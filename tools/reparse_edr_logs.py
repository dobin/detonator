import json
import logging
from typing import List, Dict

from detonatorapi.database import get_db, Submission
from detonatorapi.agent.agent_interface import parsers


logger = logging.getLogger(__name__)


def reparse_edr_logs():
    db = get_db()
    submissions = db.query(Submission).all()
    for submission in submissions:
        #if not submission.edr_logs:
        #    continue
        edr_logs = submission.edr_logs

        edr_summary: List[Dict] = []
        result_is_detected = ""

        edr_plugin_log: str = ""
        try:
            if edr_logs:
                edr_plugin_log = json.loads(edr_logs).get("logs", "")

                # EDR logs summary
                for parser in parsers:
                    parser.load(edr_plugin_log)
                    if parser.is_relevant():
                        if parser.parse():
                            edr_summary = parser.get_summary()
                            if submission.profile.edr_collector == "RedEdr":
                                result_is_detected = ""
                            elif parser.is_detected():
                                result_is_detected = "detected"
                            else:
                                result_is_detected = "clean"
                        break

        except Exception as e:
            logger.error(edr_logs)
            logger.error(f"Error parsing Defender XML logs: {e}")

        print(f"Reparsed submission {submission.id}: {result_is_detected}")
        #print(f"  {edr_summary}")

        submission.edr_summary = edr_summary
        submission.result = result_is_detected
        db.commit()

    db.close()


if __name__ == "__main__":
    reparse_edr_logs()
     
