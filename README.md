# driver-mistake-identification

In order for lane_detection to work:

1. Download weights from https://github.com/Turoad/lanedet/releases/tag/1.0

2. cd into /lane_detection/lanedet/, use the environment.yaml to create a new conda env and activate the library as a module.
`cd ./lane_detection/lanedet/`
`conda env create -f environment.yml`
`pip install -e .`

3. Run inference
`python tools/detect.py {CONFIG_DIR e.g. configs/resa/resa34_culane.py} (--img {IMAGE_DIR} OR --vid {VID_DIR}) --load_from {WEIGHTS.pth} --savedir ./vis`