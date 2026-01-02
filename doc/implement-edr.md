# Implement new EDR

There are two ways to get the EDR data: 
* Local log events gathered by DetonatorAgent, and then parsed by Detonator
* Cloud log events gathered by Detonator


## Local Log Events

This is implemented by DetonatorAgent. See its documentation how to implement it. 

The DetonatorAgent API `/api/logs/edr` will return the data.



## Cloud Log Events

Some EDRs may (also) generate logs not locally, but in the cloud. 
Detonator can retrieve these logs too. 

See `detonatorapi/edr_cloud/`, mostly with the API: 

```
class EdrCloud:
    def __init__(self):
        self.submission_id: int = 0

    @staticmethod
    def is_relevant(profile_data: dict) -> bool:
        return False
    
    def start_monitoring_thread(self, submission_id: int):
        pass
```

Where: 
* `is_relevant()`: Checks in the profile if that specific EDR is configured
* `start_monitoring_thread()`: Starts a thread which will periodically check in the background for new events in the cloud, and translate it into `SubmissionAlert`s in the DB as above. 

