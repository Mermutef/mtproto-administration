import threading


def get_xui_client():
    client = getattr(get_xui_client._local, 'client', None)
    if client is None:
        try:
            from app.x_ui_manager import XUIClient
            get_xui_client._local.client = XUIClient()
        except Exception as e:
            import logging
            logging.error(f"❌ Не удалось инициализировать XUIClient: {e}")
            get_xui_client._local.client = False
        client = get_xui_client._local.client
    return client if client is not False else None


get_xui_client._local = threading.local()
