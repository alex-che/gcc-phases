# gcc-phases
The script scans build log files of GCC running with the `-ftime-report` flag,
and output compilation phases timings for each unit and across all the units,
with the different sort and filtering possibilites. It can also produce comparison
output provided two log files instead of one. 
By default it uses CMake log file format, but it has the `--unit-line` command
line argument to allow parsing arbitrary log files.

The script may be useful to analyse what takes most time during compilation.


## Preparation
To produce the needed log you first need to add the `-ftime-report` flag to GCC.
In CMakeLists.txt it can be done by `add_compile_options(-H)` CMake command.  


## Usage
After building your project and having the build log file, you can run the script like this

```shell
> gcc-phases.py log.txt
```
(You may need to prefix that command with `python3` or `py -3` depending on how 
Python is set up on your system).

Below is an example of possible output (with some lines dropped down):

```shell
0 : src/source0.cpp.o
   phase opt and generate                   :   92.2 s. ( 90 %)
   deferred                                 :    4.6 s. (  5 %)
   template instantiation                   :    4.6 s. (  5 %)
   integration                              :    4.3 s. (  4 %)
   ...
  TOTAL :  101.9 s. =  1.7 m.

...

100 : src/source100.cpp.o
   phase opt and generate                   :    0.1 s. ( 63 %)
   rest of compilation                      :    0.0 s. ( 25 %)
   deferred                                 :    0.0 s. ( 12 %)
   ...
  TOTAL :    0.1 s. =  0.0 m.

PHASES SUMMARY
   phase opt and generate                   : 1577.5 s. = 26.3 m. ( 74 %)
   template instantiation                   :  246.5 s. =  4.1 m. ( 12 %)
   phase parsing                            :  228.3 s. =  3.8 m. ( 11 %)
   ...
  TOTAL : 2118.4 s. = 35.3 m. 
```


## Comparing two logs
You can also pass two log files to the script and it will output information
form both for comparison. It may be useful to analyse the impact of
changes done to the build process, like switch to using precompiled headers.

```shell
> gcc-phases.py log.txt log2.txt
```
Below is an example of possible output (with some lines dropped down):

```shell
0 : src/source0.cpp.o
   phase parsing                            :    0.7 s. (  4 %)  --->    11.0 s. ( 39 %)
   preprocessing                            :    0.1 s. (  1 %)  --->     5.6 s. ( 20 %)
   parser (global)                          :    0.0 s. (  0 %)  --->     1.5 s. (  5 %)
   ...
  TOTAL :   18.4 s. =  0.3 m.  --->    28.6 s. =  0.5 m.
...

100 : src/source100.cpp.o
   phase parsing                            :    0.0 s. (  1 %)  --->     0.3 s. ( 71 %)
   preprocessing                            :    0.0 s. (  0 %)  --->     0.1 s. ( 29 %)
   parser (global)                          :    0.0 s. (  0 %)  --->     0.1 s. ( 13 %)
   ...
  TOTAL :    5.2 s. =  0.1 m.  --->     0.4 s. =  0.0 m.

PHASES SUMMARY
   phase parsing                            :  228.3 s. =  3.8 m. ( 11 %)  --->  1119.7 s. = 18.7 m. ( 43 %)
   preprocessing                            :   88.0 s. =  1.5 m. (  4 %)  --->   548.1 s. =  9.1 m. ( 21 %)
   parser (global)                          :   25.8 s. =  0.4 m. (  1 %)  --->   158.0 s. =  2.6 m. (  6 %)
   ...
   integration                              :   85.1 s. =  1.4 m. (  4 %)  --->    62.2 s. =  1.0 m. (  2 %)
   deferred                                 :  221.4 s. =  3.7 m. ( 10 %)  --->   135.0 s. =  2.3 m. (  5 %)
   phase opt and generate                   : 1577.5 s. = 26.3 m. ( 74 %)  --->  1309.1 s. = 21.8 m. ( 50 %)
  TOTAL : 2118.4 s. = 35.3 m.  --->  2619.2 s. = 43.7 m.
```

## Using with different log formats
By default the script assumes the log is in CMake format. 
Specifically, it assumes that each unit's part in the log starts with line, ending with
```
[  1%] Building CXX object path/source.cpp.o
```
When the script gets this line during parsing process, it parses the source unit path and starts
gathering statistics for this unit.
To make the script use another format of such a line, you need to use command line argument `--unit-line`,
which allows to pass Python regular expression, wchich then will we used in re.search().
The regular expression needs to contain one capture group for unit's path.
E.g., the default unit line format for CMake is `'\[[\d ]+%\] Building [^ ]+ object (.+)$'`.


## Command line help
The script supports several other command line parameters, which may be useful.
```shell
> python3 --help
usage: gcc-phases.py [-h] [--include INCLUDE] [--exclude EXCLUDE]
                     [--include-phase INCLUDE_PHASE]
                     [--exclude-phase EXCLUDE_PHASE] [--from-line FROM_LINE]
                     [--to-line TO_LINE] [--sort SORT] [--desc] [--asc]
                     [--limit LIMIT] [--sort-phases {time,name}]
                     [--min-valuable-unit-time MIN_VALUABLE_UNIT_TIME]
                     [--min-valuable-phase-time MIN_VALUABLE_PHASE_TIME]
                     [--unit-line UNIT_LINE] [-v]
                     path [path2]

Parses CMake log (or other type, if provided with appropriate --unit-line) and
prints GCC compilation phases (produced by GCC -ftime-report flag).

positional arguments:
  path                  path to the CMake log file
  path2                 path to the second CMake log file for comparison

optional arguments:
  -h, --help            show this help message and exit
  --include INCLUDE     process units with paths matching re.search() regex;
                        may be used multiple times
  --exclude EXCLUDE     don't process units with paths matching re.search()
                        regex; may be used multiple times
  --include-phase INCLUDE_PHASE
                        show only phases matching re.search() regex; may be
                        used multiple times
  --exclude-phase EXCLUDE_PHASE
                        don't show phases matching re.search() regex; may be
                        used multiple times
  --from-line FROM_LINE
                        process only log lines, starting (inclusive) from the
                        provided 1-based index
  --to-line TO_LINE     process only log lines, ending (inclusive) with the
                        provided 1-based index
  --sort SORT, -s SORT  phase to sort by or 'total' or 'path'; add % at the
                        end of a phase name to use phase percentage instead of
                        time
  --desc                sort units in descending order
  --asc                 sort units in ascending order
  --limit LIMIT, -l LIMIT
                        limit output by number of units
  --sort-phases {time,name}
                        sort phases either by time or by name
  --min-valuable-unit-time MIN_VALUABLE_UNIT_TIME
                        consider phase % only for units with total time not
                        less than provided
  --min-valuable-phase-time MIN_VALUABLE_PHASE_TIME
                        consider phase % only for phases with time not less
                        than provided
  --unit-line UNIT_LINE
                        python regexp pattern for re.search() to detect the
                        line where a new unit compilation starts and capture
                        the unit's path; pattern must have one capture group
                        for the unit's path; default is CMake log line pattern
                        '\[[\d ]+%\] Building [^ ]+ object (.+)$'
  -v                    verbose mode
```