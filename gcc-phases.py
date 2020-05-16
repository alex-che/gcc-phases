# A script which scans CMake log (or other, with some tweaks) 
# and outputs GCC compilation phases (-ftime-report) for each unit, 
# with some output filters.
# May be useful to analyse what takes most time during compilation.
# To produce the log you need to add -ftime-report flag to GCC 
# (add_compile_options(-H) in CMakeLists.txt).
# CMake Tools log is usually found in ~/.local/share/CMakeTools/log.txt.

import argparse
import re
import sys

def noprint(*args): pass
verbose = noprint
args = None
def getarg(arg, default=None): 
   value = getattr(args, arg, None)
   return default if value is None else value

def create_parser():
   parser = argparse.ArgumentParser(description=
      "Parses CMake log (or other type, if provided with appropriate --unit-line)" +
      " and prints GCC compilation phases (produced by GCC -ftime-report flag).")
   parser.add_argument('path', nargs=1, help="path to the CMake log file")
   parser.add_argument('path2', nargs='?', help="path to the second CMake log file for comparison")

   parser.add_argument('--include', action='append', 
      help="process units with paths matching re.search() regex; may be used multiple times")
   parser.add_argument('--exclude', action='append', 
      help="don't process units with paths matching re.search() regex; may be used multiple times")
   parser.add_argument('--include-phase', action='append', 
      help="show only phases matching re.search() regex; may be used multiple times")
   parser.add_argument('--exclude-phase', action='append', 
      help="don't show phases matching re.search() regex; may be used multiple times")
   parser.add_argument('--from-line', type=int, help=
      "process only log lines, starting (inclusive) from the provided 1-based index")
   parser.add_argument('--to-line', type=int, help=
      "process only log lines, ending (inclusive) with the provided 1-based index")
   parser.add_argument('--sort', '-s', default='total',
      help="phase to sort by or 'total' or 'path';" + 
         " add %% at the end of a phase name to use phase percentage instead of time")
   parser.add_argument('--desc', dest="desc", action='store_true', 
      help="sort units in descending order")
   parser.add_argument('--asc', dest="desc", action='store_false',
      help="sort units in ascending order")
   parser.set_defaults(desc=True)
   parser.add_argument('--limit', '-l', type=int,
      help="limit output by number of units")
   parser.add_argument('--sort-phases', choices=('time', 'name'), default='time',
      help="sort phases either by time or by name")
   parser.add_argument('--min-valuable-unit-time', type=float, default=5,
      help="consider phase %% only for units with total time not less than provided")
   parser.add_argument('--min-valuable-phase-time', type=float, default=1,
      help="consider phase %% only for phases with time not less than provided")
   parser.add_argument('--unit-line', help="python regexp pattern for re.search()" + 
      " to detect the line where a new unit compilation starts and capture" +
      " the unit's path; pattern must have one capture group for the unit's path;" + 
      " default is CMake log line pattern '{}'".format(
         Regexes.buildingLine.pattern.replace(r'%', r'%%')))
   parser.add_argument('-v', action='store_true', help="verbose mode")
   return parser   


def main(argv):
   global verbose, args

   parser = create_parser()
   args = parser.parse_args(argv)

   verbose = print if args.v else noprint

   if getarg('unit_line'):
      Regexes.buildingLine = re.compile(getarg('unit_line'))

   path = getarg('path')[0]
   path2 = getarg('path2')
   if not path2:
      units = collect_units(path)
      print_units(units)
   else:
      units = collect_units(path)
      units2 = collect_units(path2)
      print_units(units, units2)


class PhaseStat:
   def __init__(self, seconds, percents):
      self.wall_seconds = seconds
      self.wall_percents = percents


class UnitStat:
   def __init__(self, path):
      self.path = path
      self.phases = dict()
      self.wall_total = None


class Regexes:
   buildingLine = re.compile(r'\[[\d ]+%\] Building [^ ]+ object (.+)$')
   executionTimesLine = re.compile(r'Execution times \(seconds\)$')
   phaseLine = re.compile(r'([\(\)\|\w -]+)\:[ ]*' + 
      r'([\d\.]+)[ ]*\([ ]*([\d\.]+)%\)[ ]+usr[ ]+' + 
      r'([\d\.]+)[ ]*\([ ]*([\d\.]+)%\)[ ]+sys[ ]+' + 
      r'([\d\.]+)[ ]*\([ ]*([\d\.]+)%\)[ ]+wall[ ]+' + 
      r'([\d\.]+)[ ]*([a-zA-Z]+)[ ]*\([ ]*([\d\.]+)%\)[ ]+ggc')
   totalLine = re.compile(r'TOTAL[ ]+\:[ ]+' + 
      r'([\d\.]+)[ ]+' + 
      r'([\d\.]+)[ ]+' + 
      r'([\d\.]+)[ ]+' +
      r'([\d\.]+)[ ]+([a-zA-Z]+)')
   other = dict()


def collect_units(path):
   units = dict()
   current_path = None
   current = None
   def numgroup(index): return float(m.group(index))
   def strgroup(index): return m.group(index).strip()
   from_line = getarg('from_line', 0)
   to_line = getarg('to_line', 1e+15) # some big num, never expected to be exceeded
   line_index = 0
   with open(path) as file:
      for line in file:
         line_index += 1
         if line_index < from_line:
            continue
         if line_index > to_line:
            break
         verbose("processing line", line_index, ":", line)
         if current:
            m = Regexes.phaseLine.search(line)
            if m:
               verbose("parsed as phase line")
               phase_name = strgroup(1)
               if is_phase_allowed(phase_name):
                  current.phases[phase_name] = PhaseStat(numgroup(6), numgroup(7))
               else:
                  verbose("phase '{}' dropped by cmdline argument filter".format(
                     phase_name))
               continue
            m = Regexes.totalLine.search(line)
            if m:
               verbose("parsed as total line")
               current.wall_total = numgroup(3)
               if is_unit_allowed(current.path):
                  units[current.path] = current
               else:
                  verbose("path '{}' dropped by cmdline argument filter".format(
                     current_path
                  ))
               current = None
               current_path = None
               continue
         if current_path:
            m = Regexes.executionTimesLine.search(line)
            if m:
               verbose("parsed as execution stat header line")
               current = UnitStat(current_path)
               continue
         m = Regexes.buildingLine.search(line)
         if m:
            verbose("parsed as unit building initial line")
            current_path = strgroup(1)
            current = None
            continue
   return units


def create_sum_unit(units):
   sum_unit = UnitStat("PHASES SUMMARY")
   sum_unit.wall_total = 0
   for u in units:
      sum_unit.wall_total += u.wall_total
      for k,v in u.phases.items():
         if k not in sum_unit.phases:
            sum_unit.phases[k] = PhaseStat(v.wall_seconds, None)
         else:
            sum_unit.phases[k].wall_seconds += v.wall_seconds
   # sum_unit.wall_total = sum(p.wall_seconds for p in sum_unit.phases.values())
   for p in sum_unit.phases.values():
      p.wall_percents = p.wall_seconds * 100.0 / sum_unit.wall_total
   return sum_unit


def create_diff_unit(unit1, unit2):
   def diff(u1, u2, attr): return getattr(u2, attr, 0) - getattr(u1, attr, 0)
   diff_unit = UnitStat(unit1.path if unit1 else unit2.path)
   diff_unit.wall_total = diff(unit1, unit2, 'wall_total')
   phases1 = getattr(unit1, 'phases', dict()) 
   phases2 = getattr(unit2, 'phases', dict())
   phases_names = set(phases1.keys()) | set(phases2.keys()) 
   for phase_name in phases_names:
      phase1 = phases1.get(phase_name, None)
      phase2 = phases2.get(phase_name, None)
      diff_unit.phases[phase_name] = PhaseStat(
         diff(phase1, phase2, 'wall_seconds'), 0)
   return diff_unit


def create_diff_units(units1, units2):
   keys = set(units1.keys()) | set(units2.keys())
   diff_units = dict()
   for key in keys:
      diff_units[key] = create_diff_unit(
         units1.get(key, None), units2.get(key, None)) 
   return diff_units


def is_unit_allowed(path):
   return is_str_included_by_args(path, 'include', 'exclude')


def is_phase_allowed(name):
   return is_str_included_by_args(name, 'include_phase', 'exclude_phase')


def is_str_included_by_args(str, arg_include, arg_exclude):
   includeRegexes = Regexes.other.get(arg_include, None)
   if includeRegexes is None:
      includeRegexes = Regexes.other[arg_include] = [
         re.compile(i) for i in getarg(arg_include, [])]
      Regexes.other[arg_include] = includeRegexes
   excludeRegexes = Regexes.other.get(arg_exclude, None)
   if excludeRegexes is None:
      excludeRegexes = Regexes.other[arg_exclude] = [
         re.compile(i) for i in getarg(arg_exclude, [])]
      Regexes.other[arg_exclude] = excludeRegexes
   if includeRegexes and not any(i.search(str) for i in includeRegexes):
      return False
   if excludeRegexes and any(i.search(str) for i in excludeRegexes):
      return False
   return True


def unit_sort_value(unit):
   key = getarg('sort')
   if key == 'total':
      return unit.wall_total
   if key == 'path':
      return unit.path
   phase = unit.phases.get(key.rstrip('%'), None)
   if not phase:
      return 0
   if '%' not in key:
      return phase.wall_seconds
   return phase.wall_percents if (
      phase.wall_seconds >= getarg('min_valuable_phase_time') and 
      unit.wall_total >= getarg('min_valuable_unit_time')) else 0


# def units_diff_sort_value(unit1, unit2):
#    def get(u, attr, default=None):
#       return getattr(u, attr) if u else default
#    def diff(u1, u2, attr):
#       return get(u1, attr, 0) - get(u2, attr, 0)
#    key = getarg('sort')
#    if key == 'total':
#       return diff(unit2, unit1, 'wall_total')
#    if key == 'path':
#       return get(unit1, 'path') or get(unit2, 'path')
#    phase1 = get(unit1, 'phases', dict()).get(key.rstrip('%'), None)
#    phase2 = get(unit2, 'phases', dict()).get(key.rstrip('%'), None)
#    if not phase1 and not phase2:
#       return 0
#    if '%' not in key:
#       return diff(phase2, phase1, 'wall_seconds')
#    if (get(phase1, 'wall_seconds') >= getarg('min_valuable_phase_time') and
#        get(phase2, 'wall_seconds') >= getarg('min_valuable_phase_time') and
#        get(unit1, 'wall_total') >= getarg('min_valuable_unit_time') and
#        get(unit2, 'wall_total') >= getarg('min_valuable_unit_time')):
#       return diff(phase2, phase1, 'wall_percents')
#    return 0


def phase_sort_value(name, phase):
   key = getarg('sort_phases')
   return name if key == 'name' else phase.wall_seconds


def phase_sort_order_reversed():
   key = getarg('sort_phases')
   return key == 'time'


def print_units(units, units2=None):
   if units2 is None:
      sorted_units_names = sorted(units.keys(), 
         key=lambda n: unit_sort_value(units[n]), reverse=args.desc)
   else:
      diff_units = create_diff_units(units, units2)
      sorted_units_names = sorted(diff_units.keys(), 
         key=lambda n: unit_sort_value(diff_units[n]), reverse=args.desc)

   def time_str(sec, with_mins=True):
      if sec is None: return " " * (19 if with_mins else 9)
      s = "{:>6.1f} s.".format(sec)
      if with_mins:
         s += " = {:>4.1f} m.".format(sec / 60)
      return s

   def time_diff_str(sec1, sec2, with_mins=True):
      return "  --->  ".join(time_str(s, with_mins) for s in [sec1, sec2])

   def timing_str(phase, with_mins):
      if phase is None: return time_str(None, with_mins) + " " * 8
      return (time_str(phase.wall_seconds, with_mins) + 
         " ({:>3.0f} %)".format(phase.wall_percents))

   def timing_diff_str(phase1, phase2, with_mins):
      return "  --->  ".join(timing_str(s, with_mins) for s in [phase1, phase2])

   def phase_str(phase_name, phase, with_mins):
      return "   {:<40} : {}".format(phase_name, timing_str(phase, with_mins))

   def phase_diff_str(phase_name, phase1, phase2, with_mins):
      return "   {:<40} : {}".format(
         phase_name, timing_diff_str(phase1, phase2, with_mins))

   def print_unit(unit, index=None):
      print(unit.path if index is None else "{} : {}".format(index, unit.path))
      phases = unit.phases
      sorted_phases_names = sorted(phases.keys(), 
         key=lambda k: phase_sort_value(k, phases[k]),
         reverse=phase_sort_order_reversed())
      for k in sorted_phases_names:
         print(phase_str(k, phases[k], index == None))
      print("  TOTAL : {}".format(time_str(unit.wall_total)), '\n')

   def print_unit_diff(unit, unit2, diff_unit, index=None):
      print(diff_unit.path if index is None else "{} : {}".format(index, diff_unit.path))
      phases = unit and unit.phases or dict()
      phases2 = unit2 and unit2.phases or dict()
      diff_phases = diff_unit.phases
      sorted_phases_names = sorted(diff_phases.keys(), 
         key=lambda k: phase_sort_value(k, diff_phases[k]),
         reverse=phase_sort_order_reversed())
      for k in sorted_phases_names:
         print(phase_diff_str(k, phases.get(k, None), phases2.get(k, None), index == None))
      print("  TOTAL : {}".format(time_diff_str(
         unit.wall_total if unit else 0, unit2.wall_total if unit2 else 0)), '\n')

   total = len(sorted_units_names)
   limit = getarg('limit', total)
   index = 0
   for name in sorted_units_names:
      if index >= limit:
         break
      if units2 is None:
         print_unit(units[name], index)
      else:
         print_unit_diff(units.get(name, None), units2.get(name, None), 
            diff_units[name], index)
      index += 1

   if getarg('limit', 0) == 0:
      sum_unit = create_sum_unit(units.values())
      if units2 is None:
         print_unit(sum_unit)
      else:
         sum_unit2 = create_sum_unit(units2.values())
         diff_unit = create_diff_unit(sum_unit, sum_unit2)
         print_unit_diff(sum_unit, sum_unit2, diff_unit)






#================================================== script entry point
if __name__ == "__main__" :
   main(sys.argv[1:])