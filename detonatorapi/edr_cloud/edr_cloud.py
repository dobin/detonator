

class EdrCloud:
    def __init__(self):
        self.submission_id: int = 0

    @staticmethod
    def is_relevant(profile_data: dict) -> bool:
        return False
    
    def start_monitoring_thread(self, submission_id: int):
        pass

