"""Provider runtime: request mechanics kept behind the adapter boundary.

V3 `30_PROVIDER_ARCHITECTURE_AND_PLUGIN_SPEC.md` §9 / README §19: headers,
guest-session resolution, request construction, SSE parsing, and error
normalization are provider-internal. The Core must never import from here.
"""
