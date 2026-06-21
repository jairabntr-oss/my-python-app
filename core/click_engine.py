class ClickEngine:
    def __init__(self):
        self.clicks = []

    def register_click(self, click_data):
        self.clicks.append(click_data)

    def get_clicks(self):
        return self.clicks

    def clear_clicks(self):
        self.clicks.clear()