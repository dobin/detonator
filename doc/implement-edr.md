# Implement new EDR

There are two ways to get the EDR data: 
* Local log events gathered by DetonatorAgent, and then parsed by Detonator
* Cloud log events gathered by Detonator


## Local Log Events

This is implemented by DetonatorAgent. See its documentation how to implement it. 

The DetonatorAgent API `/api/logs/edr` will return the data as string.

For example, for Defender, it will look like this (beautified XML):
```
<Event
	xmlns='http://schemas.microsoft.com/win/2004/08/events/event'>
	<System>
		<Provider Name='Microsoft-Windows-Windows Defender' Guid='{11cd958a-c507-4ef3-b3f2-5fd9dfbd2c78}'/>
		<EventID>1116</EventID>
		<Version>0</Version>
		<Level>3</Level>
		<Task>0</Task>
		<Opcode>0</Opcode>
		<Keywords>0x8000000000000000</Keywords>
		<TimeCreated SystemTime='2025-07-04T14:55:39.8297448Z'/>
		<EventRecordID>39008</EventRecordID>
		<Correlation/>
		<Execution ProcessID='3196' ThreadID='8072'/>
		<Channel>Microsoft-Windows-Windows Defender/Operational</Channel>
		<Computer>DESKTOP-6ENUR41</Computer>
		<Security UserID='S-1-5-18'/>
	</System>
	<EventData>
		<Data Name='Product Name'>Microsoft Defender Antivirus</Data>
		<Data Name='Product Version'>4.18.25050.5</Data>
		<Data Name='Detection ID'>{3DC200B4-DC42-44EC-8B0C-8F88840A56A2}</Data>
		<Data Name='Detection Time'>2025-07-04T14:55:39.823Z</Data>
		<Data Name='Unused'></Data>
		<Data Name='Unused2'></Data>
		<Data Name='Threat ID'>2147728104</Data>
		<Data Name='Threat Name'>Behavior:Win32/Meterpreter.gen!D</Data>
		<Data Name='Severity ID'>5</Data>
		<Data Name='Severity Name'>Severe</Data>
		<Data Name='Category ID'>46</Data>
		<Data Name='Category Name'>Suspicious Behaviour</Data>
		<Data Name='FWLink'>https://go.microsoft.com/fwlink/?linkid=37020&amp;name=Behavior:Win32/Meterpreter.gen!D&amp;threatid=2147728104&amp;enterprise=0</Data>
		<Data Name='Status Code'>1</Data>
		<Data Name='Status Description'></Data>
		<Data Name='State'>1</Data>
		<Data Name='Source ID'>2</Data>
		<Data Name='Source Name'>System</Data>
		<Data Name='Process Name'>Unknown</Data>
		<Data Name='Detection User'>NT AUTHORITY\SYSTEM</Data>
		<Data Name='Unused3'></Data>
		<Data Name='Path'>behavior:_process: C:\NotWhitelisted\ShellcodeGuard-shc.exe, pid:11820:56844127554067; file:_C:\NotWhitelisted\ShellcodeGuard-shc.exe</Data>
		<Data Name='Origin ID'>1</Data>
		<Data Name='Origin Name'>Local machine</Data>
		<Data Name='Execution ID'>0</Data>
		<Data Name='Execution Name'>Unknown</Data>
		<Data Name='Type ID'>2</Data>
		<Data Name='Type Name'>Generic</Data>
		<Data Name='Pre Execution Status'>0</Data>
		<Data Name='Action ID'>9</Data>
		<Data Name='Action Name'>Not Applicable</Data>
		<Data Name='Unused4'></Data>
		<Data Name='Error Code'>0x00000000</Data>
		<Data Name='Error Description'>The operation completed successfully. </Data>
		<Data Name='Unused5'></Data>
		<Data Name='Post Clean Status'>0</Data>
		<Data Name='Additional Actions ID'>0</Data>
		<Data Name='Additional Actions String'>No additional actions required</Data>
		<Data Name='Remediation User'></Data>
		<Data Name='Unused6'></Data>
		<Data Name='Security intelligence Version'>AV: 1.431.401.0, AS: 1.431.401.0, NIS: 1.431.401.0</Data>
		<Data Name='Engine Version'>AM: 1.1.25050.6, NIS: 1.1.25050.6</Data>
	</EventData>
```

Detonator will attempt to parse with all parsers available in `detonatorapi/edr_parser/`:

```
class EdrParser:
    @staticmethod
    def is_relevant(edr_data: str) -> bool:
        raise NotImplementedError("Subclasses must implement this method.")

    @staticmethod
    def parse(edr_data: str) -> Tuple[bool, List[SubmissionAlert], bool]:
        raise NotImplementedError("Subclasses must implement this method.")
```

To implement your own parser, use `detonatorapi/edr_parser/ExampleParser.py`. 

* `is_relevant()`: Check if the data returned by is for this parser / EDR
* `parse()`: Will generate `SubmissionAlert`s (submission_alerts table in DB)

It will look like this:
```
class SubmissionAlert(Base):
    __tablename__ = "submission_alerts"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    submission_id: Mapped[int] = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    source: Mapped[str] = Column(String(64), nullable=False)
    raw: Mapped[str] = Column(Text, nullable=False)

    alert_id: Mapped[str] = Column(String(128), nullable=False)
    title: Mapped[Optional[str]] = Column(String(256), nullable=False)
    severity: Mapped[Optional[str]] = Column(String(64), nullable=False)
    category: Mapped[Optional[str]] = Column(String(64), nullable=False)
    detection_source: Mapped[Optional[str]] = Column(String(64), nullable=False)
    detected_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=False)
    additional_data: Mapped[dict] = Column(JSON, nullable=True)

    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    submission: Mapped[Submission] = relationship("Submission", back_populates="alerts")
```


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

