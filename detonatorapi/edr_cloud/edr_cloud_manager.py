from typing import List, Optional, Type
from detonatorapi.edr_cloud.mde_cloud_plugin import CloudMdePlugin
from .edr_cloud import EdrCloud


edr_cloud_plugins: List[Type[EdrCloud]] = [
    CloudMdePlugin,
]


def get_relevant_edr_cloud_plugin(submission_data: dict) -> Optional[EdrCloud]:
    for plugin in edr_cloud_plugins:
        if plugin.is_relevant(submission_data):
            return plugin()
    return None

