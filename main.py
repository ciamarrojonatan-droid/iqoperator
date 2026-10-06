from bot import Bot
import cockpit

if __name__ == "__main__":
    try:
        cockpit.start_in_thread()
        print("=== Cockpit Web iniciado em http://localhost:8080 ===")
    except Exception as e:
        print(f"Aviso ao iniciar Cockpit: {e}")
    Bot().run()
