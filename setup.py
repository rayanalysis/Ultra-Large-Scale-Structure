from setuptools import setup

setup(
    name = "Ultra-Large-Scale-Structure",
    version = "1.0.0",
    options = {
        "build_apps" : {
            "include_patterns" : [
                "**/*.bam",
                "**/*.cur",
                "**/*.ttf",
                "**/*.glsl",
                "fonts/*",
            ],
			"exclude_patterns" : [
                "dist/*",
                ".git/*",
                "*__pychache__*",
                "README.md",
                "requirements.txt",
                "setup.py"
            ],
            "gui_apps" : {
                "ULSS" : "dmgalaxy.py"
            },
            "platforms" : [
                "manylinux2014_x86_64",
                #"macosx_10_6_x86_64",
                "win_amd64"
            ],
        }
    }
)
