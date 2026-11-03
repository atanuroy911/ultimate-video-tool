"""Chrome launch adapter: select a physical Vulkan device for Linux renders."""
import os
import sys


def arguments(values):
    if any(value in ('--use-angle=swiftshader','--use-vulkan=swiftshader') for value in values):return values
    result=[value for value in values if not value.startswith(('--use-angle=','--use-vulkan='))]
    return [*result,'--use-angle=vulkan','--use-vulkan=native']


if __name__=='__main__':
    chrome=os.environ['VT_RENDER_CHROME_REAL']
    os.execv(chrome,[chrome,*arguments(sys.argv[1:])])
