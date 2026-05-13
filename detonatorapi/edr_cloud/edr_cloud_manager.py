from typing import List, Optional, Type

from .edr_cloud import EdrCloud
from detonatorapi.edr_cloud.elastic_cloud_plugin import CloudElasticPlugin
from detonatorapi.edr_cloud.mde_cloud_plugin import CloudMdePlugin
from detonatorapi.edr_cloud.crowdstrike_cloud_plugin import CloudCrowdstrikePlugin


edr_cloud_plugins: List[Type[EdrCloud]] = [
    CloudMdePlugin,
    CloudElasticPlugin,
    CloudCrowdstrikePlugin,
]


def get_relevant_edr_cloud_plugin(submission_data: dict) -> Optional[EdrCloud]:
    for plugin in edr_cloud_plugins:
        if plugin.is_relevant(submission_data):
            return plugin()
    return None

