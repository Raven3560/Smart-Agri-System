"""Start the SmartAgri AI web application.

    python run.py                 # http://127.0.0.1:5000
    python run.py --host 0.0.0.0  # also reachable from phones on the same Wi-Fi
    python run.py --host 0.0.0.0 --https
                                  # HTTPS with a temporary certificate, needed for the
                                  # live camera scan on phones (accept the browser warning)
"""
import argparse

from agri import create_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Smart Agriculture Assistant")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--https", action="store_true",
                        help="serve over HTTPS with a self-signed certificate (lets phones use the camera)")
    args = parser.parse_args()
    app = create_app()
    scheme = "https" if args.https else "http"
    print(f"\n  SmartAgri running at {scheme}://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}")
    if args.host == "0.0.0.0":
        import socket
        try:
            ip = socket.gethostbyname(socket.gethostname())
            print(f"  On a phone on the same Wi-Fi: {scheme}://{ip}:{args.port}")
        except OSError:
            pass
    print("  Demo login: demo@smartagri.local / demo1234\n")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True,
            ssl_context="adhoc" if args.https else None)
