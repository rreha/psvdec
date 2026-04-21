# psvdec (formerly known as psvcdc)
psvdec is a Python program that decrypts the **PFS and eboot.bin encryption** of **PS Vita** content (games, game updates, DLC).<br>

# Download
Check out the **[latest release page](https://github.com/rreha/psvdec/releases/latest)**.

# Installation & Usage
## Installation
**You need to have Python installed on your system.**<br>
**FOR WINDOWS: You have to install [Visual C++ Redistributables](https://aka.ms/vs/17/release/vc_redist.x64.exe) in order to run psvpfsparser which is required by psvdec to work properly.**<br>
**FOR MACOS: Intel MacOS is not supported (for now). You have to install boost@1.85, curl, libtomcrypt and zlib using Homebrew in order to run psvpfsparser which is required by psvdec to work properly.** ```brew install boost@1.85 curl libtomcrypt zlib```<br>

Clone the repository and install required modules:<br>
```
git clone https://github.com/rreha/psvdec
cd psvdec
pip install -r ./requirements.txt
```
## Usage
**Drag and drop a PS Vita .pkg/folder into the script.py or use your desired CLI and specify PS Vita .pkg/folder(s).** <br><br>
e.g. : `script.py file.pkg` / `script.py [addcont/app/patch]` <br><br>
**Make sure to save the content inside the "Decrypted" folder every time you run the script.**

# Binary Sources
## psvpfsparser
Windows and Ubuntu binaries were taken from the [psvpfstools release](https://github.com/motoharu-gosuto/psvpfstools/releases/latest).<br/>
The MacOS ARM binary was built by me using [my psvpfstools fork](https://github.com/rreha/psvpfstools).

# Credits
renascene.com for the **[PS Vita Excel Spreadsheet](https://renascene.com/psv/info/card/9999)**.<br>
mmozeiko for **[pkg2zip](https://github.com/mmozeiko/pkg2zip)**.<br>
st4rk for **[PkgDecrypt](https://github.com/st4rk/PkgDecrypt)**.<br>
motoharu-gosoto for **[psvpfstools](https://github.com/motoharu-gosuto/psvpfstools)**.<br>
uyjulian for the **[fork of psvpfstools](https://github.com/uyjulian/psvpfstools)**.<br>
Team Molecule for the **[sceutils](https://github.com/TeamMolecule/sceutils)**.<br>
mathieulh for the **[sceutils fork with proper keys](https://github.com/mathieulh/sceutils)**.<br>
Yoti for the **[fixed fork of mathieulh's sceutils fork](https://github.com/RealYoti/sceutils/tree/master)**.<br>
