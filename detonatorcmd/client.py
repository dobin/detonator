


class DetonatorClient:
    def __init__(self, baseUrl, token, debug=False):
        self.baseUrl = baseUrl
        self.token = token
        self.debug = debug


    def get_profiles(self):
        raise NotImplementedError("This method should be implemented by subclasses")
    

    def valid_profile(self, profile_name):
        raise NotImplementedError("This method should be implemented by subclasses")


    def scan_file(self, filename, source_url, file_comment, scan_comment, project, profile_name, password, runtime, malware_path="", randomize_filename=True):
        raise NotImplementedError("This method should be implemented by subclasses")
