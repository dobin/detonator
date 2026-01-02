import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
import requests


class ElasticCloudClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key


    def fetch_alerts(
        self,
        hostname: Optional[str],
        start_time: datetime,
        end_time: datetime,
    ) -> List[dict]:
        # Build the search query for Elastic SIEM signals
        # curl -k -H "Authorization: ApiKey bbbb==" \
        #   -X GET "https://10.10.20.20:9200/.siem-signals-*/_search" \
        #   -H "Content-Type: application/json" \
        #   -d '{
        #     "size": 10,
        #     "query": {
        #       "bool": {
        #         "must": [
        #           { "range": { "kibana.alert.original_time": { "gte": "2025-12-31T23:00:00.000Z", "lte": "2026-01-01T22:59:59.999Z" } } },
        #           { "term": { "host.name": "desktop-h79u9ft" } }
        #         ]
        #       }
        #     }
        #   }'

        # Filter on: 
        # - hostname
        # - time range for alert original time!
        query_body = {
            "size": 32,
            "query": {
                "bool": {
                    "must": [ { 
                        "range": { 
                            "kibana.alert.original_time": {
                                "gte": start_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                                "lte": end_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                            } 
                        }
                        }, { 
                            "term": { 
                                "host.name": hostname,
                            } 
                        }]
                }
            }
        }
        
        # Make request to .siem-signals-* index
        headers = {
            "Authorization": f"ApiKey {self.api_key}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url.rstrip('/')}/.siem-signals-*/_search"
        response = requests.get(url, headers=headers, json=query_body, verify=False, timeout=15)
        
        if response.status_code >= 400:
            raise RuntimeError(f"Elastic API GET {url} failed: {response.status_code} {response.text}")
        
        return response.json().get("hits", {}).get("hits", [])
    


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Example usage
    elastic_client = ElasticCloudClient(
        base_url="https://your-elastic-cloud-instance:9200",
        api_key="your_api_key_here"
    )
    
    start = datetime.utcnow() - timedelta(hours=1)
    end = datetime.utcnow()
    
    alerts = elastic_client.fetch_alerts(
        hostname="example-hostname",
        start_time=start,
        end_time=end
    )
    
    for alert in alerts:
        logger.info(alert)
