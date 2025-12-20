import json
import logging
from typing import List, Dict

from detonatorapi.database import get_db, Submission
from detonatorapi.agent.agent_interface import parsers


logger = logging.getLogger(__name__)


def reparse_edr_telemetry_raw():
    db = get_db()
    submissions = db.query(Submission).all()
    for submission in submissions:
        #if not submission.edr_telemetry_raw:
        #    continue
        edr_telemetry_raw = submission.edr_telemetry_raw

        edr_alerts: List[Dict] = []
        result_is_detected = ""

        edr_plugin_log: str = ""
        try:
            if edr_telemetry_raw:
                edr_plugin_log = json.loads(edr_telemetry_raw).get("logs", "")

                # EDR logs summary
                for parser in parsers:
                    parser.load(edr_plugin_log)
                    if parser.is_relevant():
                        if parser.parse():
                            edr_alerts = parser.get_summary()
                            if submission.profile.edr_collector == "RedEdr":
                                result_is_detected = ""
                            elif parser.is_detected():
                                result_is_detected = "detected"
                            else:
                                result_is_detected = "clean"
                        break

        except Exception as e:
            logger.error(edr_telemetry_raw)
            logger.error(f"Error parsing Defender XML logs: {e}")

        print(f"Reparsed submission {submission.id}: {result_is_detected}")
        #print(f"  {edr_alerts}")

        submission.edr_alerts = edr_alerts
        submission.result = result_is_detected
        db.commit()

    db.close()


if __name__ == "__main__":
    reparse_edr_telemetry_raw()
     
