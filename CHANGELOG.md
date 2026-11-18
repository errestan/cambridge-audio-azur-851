# Changelog

## [0.2.0](https://github.com/errestan/cambridge-audio-azur-851/compare/v0.1.0...v0.2.0) (2026-11-18)


### Features

* add a display brightness select ([2c4acd5](https://github.com/errestan/cambridge-audio-azur-851/commit/2c4acd5626c458c405508cd43c34f84e4c526602))
* expose balance, speakers, Direct and tape monitor ([c11b4d3](https://github.com/errestan/cambridge-audio-azur-851/commit/c11b4d35d977177e8760a953d2f7755c0be5051f))
* learn the current volume on connect and reconnect ([41fa7c6](https://github.com/errestan/cambridge-audio-azur-851/commit/41fa7c605eef3209d9bfdb122de56046492d7fa5))
* verify the amplifier answers before creating the entry ([a558958](https://github.com/errestan/cambridge-audio-azur-851/commit/a5589584c27cc1243a9637540317694d24f9e6d8))


### Bug Fixes

* close the serial link quietly when Home Assistant stops ([52ed860](https://github.com/errestan/cambridge-audio-azur-851/commit/52ed860524d78dba24d928d0852eba50e0fe0b22))
* keep reconnecting whatever error opening the port raises ([0ed753a](https://github.com/errestan/cambridge-audio-azur-851/commit/0ed753a0ae83ddc9e41e49d256b77027cb45ceee))
* log commands the amp rejects and faults it reports ([149537a](https://github.com/errestan/cambridge-audio-azur-851/commit/149537ada95e50758730ca62e9778fd8159de632))
* only offer models whose command map has been verified ([b5dba91](https://github.com/errestan/cambridge-audio-azur-851/commit/b5dba9101b0d09b7d2df013840bc879b0862dd84))
* redact credentials from serial URLs in logs and errors ([f6ca79e](https://github.com/errestan/cambridge-audio-azur-851/commit/f6ca79e75582d9e2eeea24f08dc1f1abd9523103))
* report media player command failures as HomeAssistantError ([b4af3b4](https://github.com/errestan/cambridge-audio-azur-851/commit/b4af3b4bf68f24fb5377c5b7ec3781290bd1e70b))
* report standby as off instead of the deprecated standby state ([76494e2](https://github.com/errestan/cambridge-audio-azur-851/commit/76494e2aaf9e7cc04405652edccc9e8295d279dd))
* require Home Assistant 2026.7 in hacs.json ([8133386](https://github.com/errestan/cambridge-audio-azur-851/commit/8133386d82ef01e57e30dedc51bb3e18096f6056))
* select the balanced or unbalanced socket explicitly ([374d0de](https://github.com/errestan/cambridge-audio-azur-851/commit/374d0de1cefca876c9e67c19fb688476f8313ab7))
* use Home Assistant's serial port selector for ESPHome proxies ([af5fd9c](https://github.com/errestan/cambridge-audio-azur-851/commit/af5fd9c29c6ee0c06697c70196d5d18d5527dd72))
