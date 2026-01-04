# Implement new EDR

There are two ways to get the EDR data: 
* Local log events gathered by DetonatorAgent
* Cloud log events gathered by Detonator

Typically instantly-available local log files of the EDR are delivered
by local agent on DetonatorAgent. 

If the EDR generates events in a cloud / web UI or console, implement
it as cloud EDR on Detonator. 



## Local Log Events

This is implemented by DetonatorAgent. See its documentation how to implement it. 

The DetonatorAgent API `/api/logs/edr` will return the data.



## Cloud Log Events

See `detonatorapi/edr_cloud/edr_cloud.py`. 

Create like `detonatorapi/edr_cloud/myedr_plugin.py`
```python
class MyEdr(EdrCloud):
    def __init__(self):
        self.submission_id: int = 0


    @staticmethod
    def is_relevant(profile_data: dict) -> bool:
        edr_info = profile_data.get("edr_example", None)
        return edr_info is not None
    

    # initializes some kind of client for the cloud access
    # (HTTP client with authentication and REST access)
    @abstractmethod
    def InitializeClient(self, profile_data) -> bool:
        self.exampleClient = ExampleClient(
            url = profile_data.get("example_edr_url"),
            token = profile_data.get("example_edr_token"),
        )
    

    # Implement your polling (via API client above) here
    # Create a list of SubmissionAlert of your EDR
    # and store them via store_alerts()
    @abstractmethod
    def poll(self, db: Session, submission: Submission) -> bool:
        alerts = self.exampleClient.getAlerts()
        store_alerts(submission, alerts)


    # implement this to finalize monitoring, e.g., auto-close alerts
    @abstractmethod
    def finish_monitoring(self, db: Session, submission: Submission) -> bool:
        return True
    
```

The config is in the profile.data: 
```
test_myedr:
  connector: Live
  comment: MyEDR Test
  port: 8080
  vm_ip: 127.0.0.1
  data:
    edr_example:
      example_edr_url: https://myedr.cloud.com
      example_edr_token: 32432-42342-4242342
```