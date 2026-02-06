import ctypes
import os
import sys

def get_library():
    #Locate .so file for processing in the build path
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lib_path = os.path.join(base_path, "build", "libMidnightCPP.so")
    
    if not os.path.exists(lib_path):
        raise FileNotFoundError(f"C++ Library not found at {lib_path}. Did you run 'make'?")

    #Load the library
    midnight_lib = ctypes.CDLL(lib_path)

    #Define the argument and return types for verify_url_safe
    #This is crucial so Python doesn't crash the C++ side
    midnight_lib.verify_url_safe.argtypes = [ctypes.c_char_p]
    midnight_lib.verify_url_safe.restype = ctypes.c_int
    
    return midnight_lib

#Initialise the library
try:
    midnight_core = get_library()
except Exception as e:
    print(f"Error loading C++ core: {e}")
    midnight_core = None

def is_url_safe(url: str) -> bool:
    """Python wrapper to call the C++ function"""
    if not midnight_core:
        return True #Default to safe if core failed to load
        
    #Convert Python string to C-style bytes
    url_bytes = url.encode('utf-8')
    result = midnight_core.verify_url_safe(url_bytes)
    
    return bool(result)
