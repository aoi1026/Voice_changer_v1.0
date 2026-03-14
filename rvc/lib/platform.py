import os
import sys
import platform


def platform_config():
    # Use certifi's CA bundle for SSL so downloads work on Windows without user config
    try:
        import certifi
        cafile = certifi.where()
        os.environ.setdefault("SSL_CERT_FILE", cafile)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", cafile)
    except Exception:
        pass

    if sys.platform == "darwin" and platform.machine() == "arm64":
        os.environ["OMP_NUM_THREADS"] = "1"
        os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
