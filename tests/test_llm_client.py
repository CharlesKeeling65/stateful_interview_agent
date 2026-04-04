import os
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.core.llm_client import get_openai_client


class LlmClientTests(unittest.TestCase):
    @patch("app.core.llm_client.httpx", create=True)
    @patch("app.core.llm_client.OpenAI")
    def test_falls_back_to_proxy_agnostic_http_client_when_socks_support_is_missing(
        self,
        openai_cls,
        httpx_module,
    ):
        fallback_http_client = object()
        fallback_openai_client = object()

        openai_cls.side_effect = [
            ImportError(
                "Using SOCKS proxy, but the 'socksio' package is not installed. "
                "Make sure to install httpx using `pip install httpx[socks]`."
            ),
            fallback_openai_client,
        ]
        httpx_module.Client.return_value = fallback_http_client

        client = get_openai_client()

        self.assertIs(client, fallback_openai_client)
        httpx_module.Client.assert_called_once_with(trust_env=False)
        self.assertEqual(openai_cls.call_count, 2)
        self.assertEqual(
            openai_cls.call_args_list[1].kwargs["http_client"],
            fallback_http_client,
        )


if __name__ == "__main__":
    unittest.main()
