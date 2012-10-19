#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import subprocess


# Path to root FFmpeg directory.  Used as the CWD for executing all commands.
FFMPEG_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..'))

# Path to the C99 to C89 converter.
CONVERTER_EXECUTABLE = os.path.abspath(os.path.join(
    FFMPEG_ROOT, 'chromium', 'binaries', 'c99conv.exe'))

# $CC to use if GOMA can't be detected.
DEFAULT_CC = ['cl.exe']

# Disable spammy warning related to av_restrict, upstream needs to fix.
DISABLED_WARNINGS = ['-wd4005']


# Figure out if GOMA is available or not.  Kind of hacky, but well worth it
# since this will cut the run time from ~3 minutes to ~30 seconds (-j 256).
def GetCC():
  # Things that don't work:
  #   - Checking for $CC, not set and seems to be explicitly removed by gyp.
  #   - Trying to find include.gypi, as with $CC, the script is called with a
  #     sanitized environment which removes $USERPROFILE.

  # See if the user has a chromium.gyp_env setting for GOMA.
  gyp_env = os.path.abspath(os.path.join(
      FFMPEG_ROOT, '..', '..', '..', 'chromium.gyp_env'))
  if not os.path.isfile(gyp_env):
    return DEFAULT_CC

  gyp_config = eval(open(gyp_env, 'r').read())
  if 'CC' in gyp_config:
    return gyp_config['CC'].split()

  return DEFAULT_CC


def main():
  if len(sys.argv) < 3:
    print 'C99 to C89 Converter Wrapper'
    print '  usage: c99conv.py <input file> <output file> [-I <include> ...]'
    sys.exit(1)

  input_file = os.path.abspath(sys.argv[1])
  # Keep the preprocessed output file in the same directory so GOMA will work
  # without complaining about unknown paths.
  preprocessed_output_file = input_file + '_preprocessed.c'
  output_file = os.path.abspath(sys.argv[2])

  # Find $CC, hope for GOMA.
  cc = GetCC()

  # Run the preprocessor command.  All of these settings are pulled from the
  # CFLAGS section of the "config.mak" created after running build_ffmpeg.sh.
  p = subprocess.Popen(
      cc + ['-P', '-nologo', '-DCOMPILING_avcodec=1', '-DCOMPILING_avutil=1',
            '-DCOMPILING_avformat=1', '-D_USE_MATH_DEFINES',
            '-Dinline=__inline', '-Dstrtoll=_strtoi64', '-U__STRICT_ANSI__',
            '-D_ISOC99_SOURCE', '-D_LARGEFILE_SOURCE', '-DHAVE_AV_CONFIG_H',
            '-Dstrtod=avpriv_strtod', '-Dsnprintf=avpriv_snprintf',
            '-D_snprintf=avpriv_snprintf', '-Dvsnprintf=avpriv_vsnprintf',
            '-FIstdlib.h'] + sys.argv[3:] +
           DISABLED_WARNINGS +
           ['-I', '.', '-I', FFMPEG_ROOT, '-I', 'chromium/config',
            '-I', 'chromium/include/win',
            '-Fi%s' % preprocessed_output_file, input_file],
      cwd=FFMPEG_ROOT, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
  stdout, _ = p.communicate()

  # Print all lines if an error occurred, otherwise skip filename print out that
  # MSVC forces for every cl.exe execution.
  for line in stdout.splitlines():
    if p.returncode != 0 or not os.path.basename(input_file) == line.strip():
      print line

  # Abort if any error occurred.
  if p.returncode != 0:
    if os.path.isfile(preprocessed_output_file):
      os.unlink(preprocessed_output_file)
    sys.exit(p.returncode)

  # Run the converter command.  Note: the input file must have a '.c' extension
  # or the converter will crash.  libclang does some funky detection based on
  # the file extension.
  p = subprocess.Popen(
      [CONVERTER_EXECUTABLE, preprocessed_output_file, output_file],
      cwd=FFMPEG_ROOT)
  p.wait()
  os.unlink(preprocessed_output_file)
  sys.exit(p.returncode)


if __name__ == '__main__':
  main()
