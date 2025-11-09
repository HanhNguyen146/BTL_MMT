# Example usage
import json
from daemon.weaprous import WeApRous

def create_sampleapp():
    app = WeApRous()

    @app.route("/", methods=["GET"])
    def home(_):
        return {"message": "Welcome to the RESTful TCP WebApp"}

    @app.route("/user", methods=["GET"])
    def get_user(_):
        return {"id": 1, "name": "Alice", "email": "alice@example.com"}

    @app.route("/echo", methods=["POST"])
    def echo(body):
        try:
            data = json.loads(body)
            return {"received": data}
        except json.JSONDecodeError:
            return {"error": "Invalid JSON"}

    return app

if __name__ == "__main__":
    app = create_sampleapp()
    app.prepare_address("0.0.0.0", 8000)
    app.run()
