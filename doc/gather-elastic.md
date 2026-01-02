# Gather Elastic Defend Logs

## Install Elastic 

Use this guide: https://github.com/peasead/elastic-container


## Setup Elastic for Detonator Integration

Create Role `alert_reader`:
```
curl -k -u elastic:ELASTIC_PASSWORD -X POST "https://10.10.20.20:9200/_security/role/alert_reader" -H 'Content-Type: application/json' -d '{
  "indices": [
    {
      "names": [".siem-signals-*"],
      "privileges": ["read"]
    }
  ]
}'
```

Create user `alert_user` with role `alert_reader`:

```
curl -k -u elastic:ELASTIC_PASSWORD -X POST "https://10.10.20.20:9200/_security/user/alert_user" -H 'Content-Type: application/json' -d '{
  "password" : "ALERT_USER_PASSWORD",
  "roles" : ["alert_reader"],
  "full_name" : "SIEM Alert Reader",
  "email" : "alert_user@example.com"
}'
```


Create an API key for `alert_user`:

```
curl -k -u elastic:ELASTIC_PASSWORD -X POST "https://10.10.20.20:9200/_security/api_key" -H 'Content-Type: application/json' -d '{
  "name": "alert_reader_key",
  "role_descriptors": {
    "alert_reader_role": {
      "cluster": [],
      "index": [
        {
          "names": [".siem-signals-*"],
          "privileges": ["read"]
        }
      ]
    }
  }
}'
```

Response:
```
{
  "id": "ididididid",
  "name": "alert_reader_key",
  "api_key": "aaaa",
  "encoded": "bbbb=="
}
```


Test the token:
```
curl -k -H "Authorization: ApiKey bbbb==" \
  -X GET "https://10.10.20.20:9200/.siem-signals-*/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "size": 10,
    "query": {
      "range": { "@timestamp": { "gte": "2025-12-31T23:00:00.000Z", "lte": "2026-01-01T22:59:59.999Z" } }
    }
  }'
```


## Configure Detonator

```
myfirstvm:
  connector: ...
  ...
  data:
    ...
    edr_elastic:
      elastic_url: "https://10.10.20.20:9200"
      elastic_apikey: "bbbb=="
      hostname: "DESKTOP-12356"
```
