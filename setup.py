from setuptools import setup

setup(
    name='Ultra-Large-Scale-Structure',
    version='1.0.0',    
    options={
        'build_apps': {
            'include_patterns': [
                "**/*.bam",
                "**/*.ttf",
                "**/*.glsl",
                "fonts/*",
            ],
            'exclude_patterns': [
                "dist/*",
                ".git/*",
                "*__pycache__*",
                "README.md",
                "requirements.txt",
                "setup.py"
            ],
            'log_filename': '$USER_APPDATA/TryNumpy/trynumpy.log',
            'plugins': ['pandagl'],
            'gui_apps': {'ULSS': 'main.py'},
            'platforms': ['win_amd64','manylinux2014_x86_64'],
            'package_data_dirs': {
                'numpy': [('numpy.libs/*', '', {'PKG_DATA_MAKE_EXECUTABLE'})]
            }
        },
    }
)
