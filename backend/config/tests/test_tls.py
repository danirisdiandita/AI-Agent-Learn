import ssl

from django.test import SimpleTestCase


class OutboundTlsTests(SimpleTestCase):
    def test_a_plain_https_request_has_certificates_to_verify_against(self):
        # urlopen() without a context builds this default context. With no CA certificates in it, every call to
        # Google or OpenRouter fails with CERTIFICATE_VERIFY_FAILED, as it does on python.org builds of Python on macOS.
        self.assertGreater(ssl.create_default_context().cert_store_stats()["x509_ca"], 0)
