# Reverse Proxy Setup

* DetonatorApi: Main component, backend
* DetonatorUi: Web interface for DetonatorApi


DetonatorApi uses `detonatorapi/settings.yaml`:

```
$ cat detonatorapi/settings.yaml
auth_password: ""
cors_allowed_origins: http://localhost:5000,http://127.0.0.1:5000

vm_destroy_after: 60
disable_revert_vm: false
```

DetonatorUI uses `detonatorui/config.yaml`:
```
$ cat detonatorui/config.yaml
api_base_url: "http://localhost:8000"
```


## Example Config

I have the following Caddy config:

```
detonator.r00ted.ch {
        reverse_proxy http://10.10.10.10:5000
}
detonatorapi.r00ted.ch {
        reverse_proxy http://10.10.10.10:8000
}
```

DetonatorUi pointint to the API (backend):
```
api_base_url: "https://detonatorapi.r00ted.ch"
```

And allow UI access in the the API (backend):
```
cors_allowed_origins: https://detonator.r00ted.ch
```



