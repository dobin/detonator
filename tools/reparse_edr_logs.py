
from detonatorapi.database import get_db_for_thread, Scan
from detonatorapi.agent.agent_interface import parsers


def reparse_edr_logs():
    db = get_db_for_thread()
    scans = db.query(Scan).all()
    for scan in scans:
        if not scan.edr_logs:
            continue
        edr_logs = scan.edr_logs

        edr_summary = ""
        is_detected = ""

        # Check with all parsers
        for parser in parsers:
            parser.load(edr_logs)
            if parser.is_relevant():
                if parser.parse():
                    edr_summary = parser.get_summary()
                    if parser.is_detected():
                        is_detected = "detected"
                    else:
                        is_detected = "clean"
                break

        print(f"Reparsed scan {scan.id}: {is_detected}")
        print(f"  {edr_summary}")

        scan.edr_summary = edr_summary
        scan.is_detected = is_detected
        db.commit()

    db.close()


if __name__ == "__main__":
    reparse_edr_logs()
     
