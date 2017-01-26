import yaml


class Config(object):
    CONSOLE_CFG = "console.yml"

    def __init__(self, fileName=CONSOLE_CFG):
        self._config = self.read_config(fileName=fileName)

    @property
    def config(self):
        return self._config

    def read_config(self, fileName):
        with open(fileName) as I:
            try:
                cfg = yaml.load(I)
            except Exception as e:
                print(e)

        return cfg

    def instrument_groups(self):
        for G in self._config["instruments"]:
            k, = G
            yield k, G[k]

    @property
    def palette(self):
        keywords = ["foreground", "background", "mono"]
        _palette = []
        for E in self._config["palette"].keys():
            t = [E]
            pi = self._config["palette"].get(E)
            for kw in keywords:
                if kw in pi:
                    t.append(pi.get(kw))
                else:
                    t.append('')

            _palette.append(tuple(t))

        return _palette

    @property
    def instruments(self):
        fl = []  # flattenedlist
        for G in self.instrument_groups():
            name, items = G
            fl = fl + items

        return fl


if __name__ == "__main__":
    cfg = Config()
    print("Config:\n", cfg.config)
    print("Instruments:\n", cfg.instruments)
    print("Palette:\n", cfg.palette)
    for G in cfg.instrument_groups():
        name, items = G
        print(items)

    print("Some trading parameters:\n")
    print(cfg.config["trading"])
