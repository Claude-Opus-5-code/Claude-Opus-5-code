"""Network-blocked tests using synthetic pools under this repository only."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import stat
import tempfile
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('syntx_refresh', BASE / '03_syntx_refresh.py')
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)
TOKEN = 'SYNTHETIC_PRIVATE_TOKEN'
ROW = {'email': 'private@example.test', 'token': TOKEN, 'status': 'active',
       'chat_uuid': 'keep', 'created_at': 'keep', 'extra': {'keep': [1, 2]}}


class Response:
    def __init__(self, status=200, body=None):
        self.status_code, self.body, self.closed = status, body, False

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body

    def close(self):
        self.closed = True


class Session:
    def __init__(self, *responses):
        self.responses, self.calls = iter(responses), []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def balance(value=5.5):
    return Response(body={'balance': value})


def limits(six=100, seven=100):
    return Response(body={'window_6h': {'percent_left': six, 'expires_at': None},
                          'window_7d': {'percent_left': seven, 'expires_at': None}})


class RefreshTests(unittest.TestCase):
    def setUp(self):
        network = patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK FORBIDDEN'))
        connect = network.start()
        self.addCleanup(network.stop)
        self.addCleanup(connect.assert_not_called)
        directory = tempfile.TemporaryDirectory(prefix='refresh_test_', dir=BASE / 'Root')
        self.addCleanup(directory.cleanup)
        self.pool = Path(directory.name) / 'accounts.json'

    def write_pool(self, rows):
        self.pool.write_text(json.dumps(rows, ensure_ascii=False, indent=4), encoding='utf-8')
        return self.pool.read_bytes()

    def run_cli(self, session, *args):
        with patch.object(refresh, 'make_session', return_value=session), contextlib.redirect_stdout(io.StringIO()) as output:
            code = refresh.main(['--file', str(self.pool), *args])
        return code, output.getvalue()

    def test_headers_endpoints_timeout_and_closure(self):
        first, second = balance(), limits()
        session = Session(first, second)
        self.assertEqual(refresh.check_account(ROW, session, 7)['state'], 'healthy')
        self.assertEqual([url for url, _ in session.calls], [refresh.API + '/user/balance', refresh.API + '/llm/limits'])
        for _, options in session.calls:
            self.assertEqual(options['headers']['Authorization'], 'Bearer ' + TOKEN)
            self.assertEqual(options['headers']['User-Agent'], refresh.USER_AGENT)
            self.assertEqual(options['timeout'], 7)
            self.assertFalse(options['allow_redirects'])
        self.assertTrue(first.closed and second.closed)

    def test_approved_http_removals_on_both_endpoints(self):
        for status in (401, 403, 429):
            for second in (False, True):
                with self.subTest(status=status, second=second):
                    prefix = [balance()] if second else []
                    session = Session(*prefix, Response(status, 'PRIVATE BODY'))
                    self.assertEqual(refresh.check_account(ROW, session)['state'], 'dead')
                    self.assertEqual(len(session.calls), 2 if second else 1)

    def test_zero_balance_and_six_hour_limit(self):
        for value, six in ((0, 100), (5.5, 0), (0.0, 0.0)):
            self.assertEqual(refresh.check_account(ROW, Session(balance(value), limits(six)))['state'], 'dead')

    def test_seven_day_zero_alone_not_deleted(self):
        self.assertEqual(refresh.check_account(ROW, Session(balance(), limits(100, 0)))['state'], 'limited')
        before = self.write_pool([ROW])
        self.run_cli(Session(balance(), limits(100, 0)), '--clean')
        self.assertEqual(self.pool.read_bytes(), before)

    def test_unapproved_http_statuses_retained(self):
        for status in (201, 301, 302, 400, 404, 408, 500, 503):
            self.assertEqual(refresh.check_account(ROW, Session(Response(status), limits()))['state'], 'unknown')

    def test_connection_and_json_failures_retained(self):
        for response in (TimeoutError(TOKEN), ConnectionError(TOKEN), Response(body=ValueError(TOKEN)), Response(body=[])):
            self.assertEqual(refresh.check_account(ROW, Session(response, limits()))['state'], 'unknown')

    def test_invalid_numeric_values_not_deletion_evidence(self):
        for value in (None, False, True, '0', -1, float('nan'), float('inf'), {}, [], 10 ** 1000):
            with self.subTest(kind=type(value).__name__):
                self.assertEqual(refresh.check_account(ROW, Session(balance(value), limits()))['state'], 'unknown')
                self.assertEqual(refresh.check_account(ROW, Session(balance(), limits(value)))['state'], 'unknown')
        self.assertEqual(refresh.check_account(ROW, Session(balance(), limits(101)))['state'], 'unknown')

    def test_missing_fields_retained(self):
        for body in ({}, {'window_6h': None}, {'window_6h': {'percent_left': 50}}):
            self.assertEqual(refresh.check_account(ROW, Session(balance(), Response(body=body)))['state'], 'unknown')

    def test_definitive_zero_overrides_other_unknown(self):
        self.assertEqual(refresh.check_account(ROW, Session(balance(0), TimeoutError()))['state'], 'dead')
        self.assertEqual(refresh.check_account(ROW, Session(TimeoutError(), limits(0)))['state'], 'dead')

    def test_invalid_tokens_never_sent_or_removed(self):
        for token in (None, '', 123, 'x\r\nHeader', 'with space', '\x7f', 'غير_ascii'):
            session = Session()
            self.assertEqual(refresh.check_account({'token': token}, session)['state'], 'unknown')
            self.assertEqual(session.calls, [])

    def test_report_preserves_bytes_and_redacts_secrets(self):
        before = self.write_pool([ROW])
        code, output = self.run_cli(Session(balance(0), limits()))
        self.assertEqual(code, 0)
        self.assertEqual(self.pool.read_bytes(), before)
        self.assertIn('المحذوف فعليًا=0', output)
        for secret in (TOKEN, ROW['email'], '\x1b'):
            self.assertNotIn(secret, output)
        self.assertEqual(list(self.pool.parent.glob('*.tmp')), [])

    def test_clean_preserves_all_fields_of_retained_rows(self):
        unknown = dict(ROW, token='unknown', status='custom')
        dead, good = dict(ROW, token='dead'), dict(ROW, token='good')
        self.write_pool([unknown, dead, good])
        code, output = self.run_cli(Session(TimeoutError(TOKEN), limits(), Response(401), balance(), limits()), '--clean')
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(self.pool.read_bytes()), [unknown, good])
        self.assertIn('المحذوف فعليًا=1', output)
        self.assertNotIn(TOKEN, output)

    def test_purge_alias_removes_all_candidates(self):
        self.write_pool([ROW])
        code, _ = self.run_cli(Session(Response(429)), '--purge')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(self.pool.read_bytes()), [])

    def test_no_candidates_no_rewrite(self):
        before = self.write_pool([ROW])
        self.assertEqual(self.run_cli(Session(balance(), limits()), '--clean')[0], 0)
        self.assertEqual(self.pool.read_bytes(), before)

    def test_empty_pool_no_transport(self):
        before = self.write_pool([])
        with patch.object(refresh, 'make_session', side_effect=AssertionError('no client')), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(refresh.main(['--file', str(self.pool), '--clean']), 0)
        self.assertEqual(self.pool.read_bytes(), before)
        self.assertIn('أقل من 5', output.getvalue())

    def test_bad_pool_no_overwrite(self):
        for raw in (b'', b'invalid', b'{}', b'[null]', b'[1]', b'\xff'):
            self.pool.write_bytes(raw)
            self.assertEqual(self.run_cli(Session(), '--clean')[0], 2)
            self.assertEqual(self.pool.read_bytes(), raw)

    def test_missing_pool_not_created(self):
        self.assertEqual(self.run_cli(Session(), '--clean')[0], 2)
        self.assertFalse(self.pool.exists())

    def test_default_path_is_sibling(self):
        self.assertEqual(refresh.DEFAULT_POOL, BASE / 'accounts_syntx.json')

    def test_replace_failure_preserves_original(self):
        before = self.write_pool([ROW])
        with patch.object(refresh.os, 'replace', side_effect=OSError('PRIVATE')):
            code, output = self.run_cli(Session(Response(401)), '--clean')
        self.assertEqual(code, 2)
        self.assertEqual(self.pool.read_bytes(), before)
        self.assertNotIn('PRIVATE', output)
        self.assertEqual(list(self.pool.parent.glob('*.tmp')), [])

    def test_serialization_failure_cleans_temporary(self):
        before = self.write_pool([ROW])
        with patch.object(refresh.json, 'dump', side_effect=OSError('mock failure')):
            with self.assertRaises(OSError):
                refresh.save_clean_pool(self.pool, [], before)
        self.assertEqual(self.pool.read_bytes(), before)
        self.assertEqual(list(self.pool.parent.glob('*.tmp')), [])

    def test_changed_snapshot_aborts(self):
        before = self.write_pool([ROW])
        after = self.write_pool([ROW, dict(ROW, token='new')])
        with self.assertRaises(ValueError):
            refresh.save_clean_pool(self.pool, [], before)
        self.assertEqual(self.pool.read_bytes(), after)

    def test_change_during_temp_write_aborts(self):
        before = self.write_pool([ROW])
        real_fsync = refresh.os.fsync
        def changed(fd):
            real_fsync(fd)
            self.pool.write_bytes(b'[]\n')
        with patch.object(refresh.os, 'fsync', side_effect=changed), self.assertRaises(ValueError):
            refresh.save_clean_pool(self.pool, [], before)
        self.assertEqual(self.pool.read_bytes(), b'[]\n')
        self.assertEqual(list(self.pool.parent.glob('*.tmp')), [])

    def test_atomic_replace_location_and_permissions(self):
        before = self.write_pool([ROW])
        self.pool.chmod(0o600)
        real_replace = os.replace
        def checked(source, target):
            self.assertEqual(Path(source).parent, self.pool.parent)
            self.assertEqual(Path(source).suffix, '.tmp')
            self.assertEqual(self.pool.read_bytes(), before)
            return real_replace(source, target)
        with patch.object(refresh.os, 'replace', side_effect=checked):
            refresh.save_clean_pool(self.pool, [], before)
        self.assertEqual(json.loads(self.pool.read_bytes()), [])
        if os.name != 'nt':
            self.assertEqual(stat.S_IMODE(self.pool.stat().st_mode), 0o600)

    def test_warning_threshold(self):
        good = refresh.check_account(ROW, Session(balance(), limits()))
        for count in (4, 5, 6):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                refresh.report([good] * count, False, 0)
            self.assertEqual('أقل من 5' in output.getvalue(), count < 5)

    def test_timeout_validation(self):
        for value in ('0', '121', 'nan', 'inf', 'bad'):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                refresh.main(['--timeout', value])
            self.assertEqual(caught.exception.code, 2)

    def test_help_no_pool_access(self):
        with patch.object(refresh, 'load_pool', side_effect=AssertionError('no pool')), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as caught:
            refresh.main(['--help'])
        self.assertEqual(caught.exception.code, 0)

    def test_har_payloads_without_using_captured_credentials(self):
        from urllib.parse import urlsplit
        count = 0
        for path in sorted((BASE / 'har').glob('*.har')):
            for entry in json.loads(path.read_text(encoding='utf-8'))['log']['entries']:
                url = urlsplit(entry['request']['url'])
                if url.hostname != 'api.syntx.ai':
                    continue
                content = entry['response'].get('content', {}).get('text', '')
                if url.path == '/api/v1/user/balance':
                    result = refresh.check_account(ROW, Session(Response(body=json.loads(content)), limits()))
                elif url.path == '/api/v1/llm/limits':
                    result = refresh.check_account(ROW, Session(balance(), Response(body=json.loads(content))))
                else:
                    continue
                self.assertIn(result['state'], ('healthy', 'dead', 'limited'))
                count += 1
        self.assertEqual(count, 37)


if __name__ == '__main__':
    unittest.main()
