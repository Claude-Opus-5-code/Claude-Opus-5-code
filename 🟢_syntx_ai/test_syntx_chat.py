"""Hermetic chat lifecycle tests: synthetic pools, no network or child processes."""
import ast
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

BASE = Path(__file__).resolve().parent
SOURCE = BASE / '01_syntx_chat.py'
ROW = {'status': 'active', 'token': 'SYNTHETIC_TOKEN', 'chat_uuid': 'test-chat'}


class NoColors:
    def __getattr__(self, name):
        return ''


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.transport = SimpleNamespace(
            get=Mock(side_effect=AssertionError('NETWORK FORBIDDEN')),
            post=Mock(side_effect=AssertionError('NETWORK FORBIDDEN')),
            Session=Mock(side_effect=AssertionError('NETWORK FORBIDDEN')),
        )
        for target, name in ((socket.socket, 'connect'), (subprocess, 'Popen'),
                             (threading.Thread, 'start')):
            blocked = self.stack.enter_context(patch.object(
                target, name, side_effect=AssertionError('SIDE EFFECT FORBIDDEN')))
            self.addCleanup(blocked.assert_not_called)
        for blocked in vars(self.transport).values():
            self.addCleanup(blocked.assert_not_called)
        spec = importlib.util.spec_from_file_location('syntx_chat_under_test', SOURCE)
        self.chat = importlib.util.module_from_spec(spec)
        self.stack.enter_context(patch.dict(sys.modules, {
            spec.name: self.chat,
            'curl_cffi': SimpleNamespace(requests=self.transport),
            'colorama': SimpleNamespace(init=Mock(), Fore=NoColors(), Style=NoColors()),
        }))
        spec.loader.exec_module(self.chat)
        folder = self.stack.enter_context(tempfile.TemporaryDirectory(
            prefix='chat_test_', dir=BASE / 'Root'))
        self.directory = Path(folder)
        self.stack.enter_context(patch.object(self.chat, 'BASE_DIR', self.directory))
        self.pool = self.directory / 'accounts_syntx.json'
        self.cfg = self.chat.Config()
        self.hook = self.stack.enter_context(patch.object(
            self.chat, 'spawn_background_refill', return_value=None))

    def write_pool(self, rows):
        self.pool.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
        return self.pool.read_bytes()

    def run_main(self, *args):
        with patch.object(sys, 'argv', [str(SOURCE), *args]), contextlib.redirect_stdout(io.StringIO()) as output:
            result = self.chat.main()
        return result, output.getvalue()

    def test_spawn_background_refill_hook_structure(self):
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        hook = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'spawn_background_refill')
        self.assertIsNotNone(hook)
        self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                             and n.func.id == hook.name for n in ast.walk(tree)))

    def test_registration_symbols_and_configuration_removed(self):
        for name in ('TempMailClubProvider', 'register_single_syntx_account',
                     'add_account_to_pool', 'refill_accounts_pool',
                     '_background_pool_refill_worker', 'start_background_account_worker'):
            self.assertFalse(hasattr(self.chat, name), name)
        for name in ('auth_token', 'chat_uuid', 'otp_timeout', 'email_provider',
                     'preferred_domains', 'auto_refill_background',
                     'background_check_interval', 'min_pool_size'):
            self.assertFalse(hasattr(self.cfg, name), name)
        source = SOURCE.read_text(encoding='utf-8')
        for removed in ('send-otp', 'verify-otp', 'temp-mail.club', 'fake_ip'):
            self.assertNotIn(removed, source)

    def test_missing_pool_exits_before_input_or_dispatch(self):
        with patch('builtins.input', side_effect=AssertionError('NO INPUT')), patch.object(
                self.chat, 'send_syntx_message', side_effect=AssertionError('NO SEND')):
            for args in ((), ('--cli',), ('hello',)):
                result, output = self.run_main(*args)
                self.assertIsNone(result)
                self.assertIn('لا توجد حسابات معتمدة جاهزة', output)
        self.assertFalse(self.pool.exists())

    def test_empty_inactive_and_malformed_pools_exit_without_writes(self):
        raw_cases = [b'[]', b'{}', b'null', b'[null]', b'[1]', b'invalid', b'\xff', b'',
                     json.dumps([dict(ROW, status='expired')]).encode('utf-8'),
                     json.dumps([dict(ROW, token=123)]).encode('utf-8')]
        with patch('builtins.input', side_effect=AssertionError('NO INPUT')):
            for raw in raw_cases:
                with self.subTest(raw=raw):
                    self.pool.write_bytes(raw)
                    _, output = self.run_main('--cli')
                    self.assertIn('لا توجد حسابات معتمدة جاهزة', output)
                    self.assertEqual(self.pool.read_bytes(), raw)

    def test_readiness_rejects_unusable_tokens(self):
        for token in (None, '', 1, False, ' ', 'x\ny', '\x7f', 'عربي'):
            self.assertFalse(self.chat.is_ready_account(dict(ROW, token=token)))
        self.assertTrue(self.chat.is_ready_account(ROW))
        self.assertFalse(self.chat.is_ready_account(dict(ROW, status='expired')))

    def test_help_does_not_read_pool(self):
        with patch.object(self.chat, 'load_accounts_pool', side_effect=AssertionError('NO POOL')):
            with self.assertRaises(SystemExit) as result:
                self.run_main('--help')
        self.assertEqual(result.exception.code, 0)

    def test_removed_registration_flags_are_rejected(self):
        for args in (('--refill',), ('--pool-size', '5')):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
                self.run_main(*args)
            self.assertEqual(result.exception.code, 2)

    def test_count_reports_ready_records_without_starting_chat(self):
        before = self.write_pool([ROW, dict(ROW, status='expired'), dict(ROW, token='')])
        with patch.object(self.chat, 'send_syntx_message', side_effect=AssertionError('NO SEND')):
            _, output = self.run_main('--count')
        self.assertIn('1 حساب جاهز', output)
        self.assertEqual(self.pool.read_bytes(), before)

    def test_existing_account_acquisition_preserves_pool(self):
        before = self.write_pool([dict(ROW, status='expired'), ROW])
        self.assertEqual(self.chat.acquire_session_token(self.cfg), ('SYNTHETIC_TOKEN', 'test-chat'))
        self.assertEqual(self.pool.read_bytes(), before)

    def test_missing_chat_id_creates_only_chat_for_existing_account(self):
        before = self.write_pool([dict(ROW, chat_uuid=None)])
        with patch.object(self.chat, 'create_syntx_chat', return_value='new-chat') as create:
            self.assertEqual(self.chat.acquire_session_token(self.cfg), ('SYNTHETIC_TOKEN', 'new-chat'))
        create.assert_called_once_with('SYNTHETIC_TOKEN', self.cfg)
        self.assertEqual(self.pool.read_bytes(), before)

    def test_out_of_pool_token_cannot_override_empty_pool(self):
        self.write_pool([])
        self.cfg.auth_token = 'OUT_OF_POOL_TOKEN'
        self.cfg.chat_uuid = 'out-of-pool-chat'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.chat.acquire_session_token(self.cfg), (None, None))

    def test_programmatic_send_with_empty_pool_returns_without_network(self):
        before = self.write_pool([])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertIsNone(self.chat.send_syntx_message('hello', self.cfg))
        self.assertIn('دون انتظار أو إنشاء حسابات', output.getvalue())
        self.assertEqual(self.pool.read_bytes(), before)

    def test_prompt_dispatch_preserves_cli_settings(self):
        before = self.write_pool([ROW])
        with patch.object(self.chat, 'send_syntx_message') as send:
            self.run_main('--model', '1', '--no-thinking', '--no-plan', '--no-search', 'hello', 'world')
        send.assert_called_once()
        prompt, cfg, label = send.call_args.args
        self.assertEqual((prompt, label), ('hello world', 'CLI Argument'))
        self.assertEqual(cfg.model, 'gpt-5.6-terra')
        self.assertFalse(cfg.thinking or cfg.plan or cfg.deep_research or cfg.enable_tools)
        self.assertEqual(self.pool.read_bytes(), before)

    def test_file_dispatch_reads_utf8(self):
        self.write_pool([ROW])
        (self.directory / 'input.txt').write_text('سؤال عربي', encoding='utf-8')
        with patch.object(self.chat, 'send_syntx_message') as send:
            self.run_main('--file', 'input.txt', '--output', 'output.txt')
        self.assertEqual(send.call_args.args[0], 'سؤال عربي')
        self.assertEqual(send.call_args.args[1].output_file, 'output.txt')

    def test_interactive_multiple_messages_never_call_hook(self):
        self.write_pool([ROW])
        with patch('builtins.input', side_effect=['first', 'second', 'exit']), patch.object(
                self.chat, 'send_syntx_message') as send:
            self.run_main('--cli')
        self.assertEqual(send.call_count, 2)

    def test_interactive_pool_depletion_exits_before_next_input(self):
        self.write_pool([ROW])
        def deplete(*args):
            self.write_pool([])
        with patch('builtins.input', side_effect=['hello']) as user_input, patch.object(
                self.chat, 'send_syntx_message', side_effect=deplete):
            _, output = self.run_main('--cli')
        user_input.assert_called_once()
        self.assertIn('لا توجد حسابات معتمدة جاهزة', output)

    def test_windows_console_guards_handle_cp1252_and_missing_reconfigure(self):
        for filename in ('01_syntx_chat.py', '03_syntx_refresh.py'):
            tree = ast.parse((BASE / filename).read_text(encoding='utf-8'))
            guard = next(n for n in tree.body if isinstance(n, ast.If)
                         and ast.unparse(n.test) == "sys.platform == 'win32'")
            compiled = compile(ast.Module(body=[guard], type_ignores=[]), filename, 'exec')
            for platform in ('win32', 'linux'):
                with io.TextIOWrapper(io.BytesIO(), encoding='cp1252') as out, io.TextIOWrapper(
                        io.BytesIO(), encoding='cp1252') as err:
                    exec(compiled, {'sys': SimpleNamespace(platform=platform, stdout=out, stderr=err)})
                    for stream in (out, err):
                        self.assertEqual(stream.encoding, 'utf-8' if platform == 'win32' else 'cp1252')
                        if platform == 'win32':
                            self.assertEqual(stream.errors, 'replace')
                            stream.write('فحص عربي')
                            stream.flush()
                            self.assertEqual(stream.buffer.getvalue().decode('utf-8'), 'فحص عربي')
            exec(compiled, {'sys': SimpleNamespace(platform='win32', stdout=io.StringIO(), stderr=io.StringIO())})


if __name__ == '__main__':
    unittest.main()
