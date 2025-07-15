# Setup Azure

THIS IS WORK IN PROGRESS. 

This will take you many hours, if not days. Be prepared. 


## Azure Preparation

* Configure `azure/config.env`
* run `azure/init_az_resource_group.sh`
* run `azure/upload_rededr.sh`
* run `azure/upload_script.sh`
* run `azure/make_vm_template.sh` 


## Configuring Detonator

* Configure `detonatorapi/settings.py` as above
* Start

You should see someting like:

```
INFO     [ MainThread                ] Azure Manager initialized successfully
```


