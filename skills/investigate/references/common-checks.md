# What to Check First, by Symptom

When a symptom matches any row below, run that row's check first, then list hypotheses. The table gives directions only; paths, hosts and install locations are whatever is actually found in the current environment.

## Runtime environment

| Symptom | What to check first | How |
|---|---|---|
| Garbled text, `UnicodeEncodeError`, `UnicodeDecodeError` | The runtime's default encoding | Force the interpreter and the shell to use UTF-8 with environment variables or startup options, and confirm whether the interpreter's isolated or safe mode ignores those environment variables. Specify the encoding explicitly when reading and writing files. Add a BOM when an older shell needs one to recognize a UTF-8 script |
| Interpreter or runtime not found, packages cannot be installed into the system environment | How packages and runtimes are managed | First find the package or environment manager the project specifies and run with it; do not try the system interpreter or a global install first |
| Interpreter path no longer valid, target directory does not exist | Tool cache | Clear that tool's cache, or rerun with the cache disabled |
| "X is not installed on this machine" | Install location | Check the package manager's global install directory, the user-level executable directory and the shell's command resolution, not only PATH |
| Command timed out | The tool's timeout setting | A timeout only shows that there was not enough time; it is not evidence of missing permission or of nothing being found, and it is not new evidence that justifies a retry. Run work that is expected to take long in the background |
| A script did what it should but returned non-zero | Exit code of the last command | Look at each command's exit code separately. A pipeline reports only the result of its last stage |

## Files and paths

| Symptom | What to check first | How |
|---|---|---|
| `unexpected EOF`, odd characters in a file, or backslashes disappearing | How the file was written | Write multi-line content, or content containing non-ASCII characters, quotes or backslashes, with an editing tool, not through shell escaping |
| A file written to a temporary path cannot be read by another program | Path mapping | Different shells can interpret the same path differently, for example `/tmp` in Git Bash on Windows. Files exchanged between programs MUST always use absolute paths |
| git reports dubious ownership | File ownership check, common on network drives and shared directories | Add `-c safe.directory=<path>` to the single command; do not change the global configuration |
| A file is locked during a build | A running program | Find the process holding the file, and confirm whether you started it |
| A scheduled job needs manual approval to read a file, or the path does not exist | How paths are written in the scheduled job | Inside the scheduled job, use paths relative to the working directory; do not write drive letters or network paths. Do a trial run after creating it |

## Services, processes and screens

| Symptom | What to check first | How |
|---|---|---|
| The port responds, but the behavior is old | What is holding the port | Check the process holding the port and its start time. Restart the service after changing generated code or configuration |
| A web page that does not reflect a change | Whether the browser actually reloaded | First add a recognizable marker to confirm you are seeing the new version; switch browsers when needed. Do not dismiss what the user sees before confirming |
| An external program hangs or pops up an error window | Leftover processes | Look at the start time and whether CPU time is still increasing to judge whether another flow left it behind. End only PIDs you started |
| "Integration tests cannot run locally" | Container environment | Confirm the container engine is running, the connection endpoint setting (for example `DOCKER_HOST`) points to the right place, and there is no leftover socket file |

## Tests and CI

| Symptom | What to check first | How |
|---|---|---|
| All green locally, red in CI | Environment differences between local and CI | Compare line endings, ignored generated files, whether installs are clean from the lockfile, and CI execution permissions |
| Many tests of the same kind fail at once | Dependencies and environment, not individual tests | Use the package manager's dependency query to see whether the same package was installed in several versions |
| End-to-end tests fail intermittently | Timing | After an action, wait for the network or screen state to settle. Record the test name, the number of reruns and the environment; do not close the issue because a rerun passed |

## Data fetching and external services

| Symptom | What to check first | How |
|---|---|---|
| Fetch returns 0 rows, everything deduplicated away, counts drop | Whether the command itself succeeded and whether the source covers the range | A pipeline swallows the exit code of the earlier command. Check for error pages with status 200, 302 redirects, whether the time range is covered, and whether the reference date was silently changed. Neither a redirect nor an empty result means no data exists |
| "This site needs JS to fetch" | The actual data requests | Use the browser's developer tools to see the API requests the page actually makes, not only one static page load |
| Private package registry returns 401 or 404 on download | Token scope | Confirm the token is set at the right host or scope level |
