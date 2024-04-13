from test_qemu_fw import test_firmware, parse_fw_arch

import argparse
import os
import re
import sys
import logging

def parse_result(result_string: str) -> bool:
    print(result_string)
    res = re.split('\r|\n', result_string)
    res = [line for line in res if line != "\n" and line != ""]

    group_checks = []
    handled_errs = []
    for line in res:
        if "UBT:" in line:
            start_of_group = "Start testing cases with "
            end_of_group = ["Checks with ", " are done"]
            if start_of_group in line:
                group = line.split(start_of_group, 1)[1]
                print(str(group[0:-3]) + " start ...")
                group_checks.append(group[0:-3])
            elif end_of_group[0] in line and end_of_group[1] in line:
                group = line.split(end_of_group[0], 1)[1].split(end_of_group[1], 1)[0]
                print(group + ": OK ...")
                if group != group_checks.pop():
                    logging.error(
                        "The order of check groups is broken! Something went wrong"
                    )
                    return False
            else:
                if len(handled_errs) == 0:
                    logging.error(
                        "The error in "
                        + group_checks[-1]
                        + ". The Undefined Behaviour Sanitizer did not work in the test:\n"
                        + line
                    )
                    return False

                ubsan_ans = handled_errs.pop(0)
                ubsan_ans = ubsan_ans.lower()
                ans = (
                    line[len("UBT:") + 1 :]
                    .lower()
                    .replace("[[ptr:0x[0-9a-f]*]]", "'{{.*}}'")
                    .split("'{{.*}}'")
                )
                for p in ans:
                    if p not in ubsan_ans:
                        logging.error(
                            "The error in group with "
                            + group_checks[-1]
                            + ". The Undefined Behaviour Sanitizer did not process the test:"
                            + line
                        )
                        return False

        if "UBSan:" in line:
            line = line.split('UBSan:')
            handled_errs += line[1:]

    print("OK")

    return True


def main():
    """The QEMU-based firmware checker"""
    parser = argparse.ArgumentParser(
        description="Run QEMU and determine whether firmware can start bootloader."
    )
    parser.add_argument("fw_path", type=str, help="Path to firmware.")
    parser.add_argument("--no-rdrand", dest="rdrand", action="store_false")
    parser.add_argument("--build-path", dest="build_path", action="store")
    parser.add_argument("--tests-dir-path", dest="tests_dir_path", action="store")
    parser.add_argument("--fw-arch", dest="fw_arch", action="store")
    parser.add_argument("--test-ubsan-group", dest="test_groups", action="store")
    parser.set_defaults(rdrand=True)
    parser.set_defaults(fw_arch="X64")
    parser.set_defaults(tests_dir_path=os.path.dirname(os.path.realpath(__file__)))
    parser.set_defaults(test_groups="UNDEFINED")
    pexpect_timeout = 10  # default 30
    
    args = parser.parse_args()
    logging.basicConfig(
        format="%(asctime)-15s [%(levelname)s] %(funcName)s: %(message)s",
        level=logging.INFO,
    )

    fw_arch = parse_fw_arch(args.fw_arch)

    groups = {
        "ALIGNMENT",
        "BUILTIN",
        "BOUNDS",
        "IMPLICIT_CONVERSION",
        "INTEGER",
        "NONNULL",
        "POINTERS",
        "UNDEFINED",
    }
    test_groups = args.test_groups.upper().split(",")
    if not set(test_groups).issubset(groups):
        parser.error(
            "you specified a non-existent test group, "
            + "you need to select groups separated by commas from the list:"
            + "'ALIGNMENT', 'BUILTIN', 'BOUNDS', 'IMPLICIT_CONVERSION' "
            + "'INTEGER', 'NONNULL', 'POINTERS', 'UNDEFINED'"
        )

    esp_dir = args.build_path
    boot_drive = "-hda fat:rw:" + esp_dir
    tests_dir = args.tests_dir_path
    
    for g in test_groups:
        print("Checking a " + g + " group ...")

        expected_string = "UBT: All tests are done..."
        print("Testing ...")
        result, result_str = test_firmware(
            args.fw_path,
            boot_drive,
            expected_string,
            pexpect_timeout,
            args.rdrand,
            fw_arch,
        )
        if result:
            tests_dir+="/ubsan_tests"
            os.makedirs(tests_dir, exist_ok=True)
            with open(tests_dir+"/"+g.lower()+".txt", "w+") as test_file:
                test_file.write(result_str)
            print("Parsing result ...")
            parse_res = parse_result(result_str)
            if not parse_res:
                sys.exit(1)
        else:
            sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
