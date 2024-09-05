<div align="center">
  <img align="center" src=".github/images/logo/PicoPortal.png" />
  <h1 align="center">Pico Portal</h1>
  <p align="center">
    Turn your Raspberry Pi Pico W into a portable, powerful Wi-Fi access point with this lightweight captive portal software. 
    Serve web content/pages and display real-time connection info directly on the onboard Pimoroni screen. Log all the connection details for later debugging and use!
  </p>
  <p align="center">
    Whether you're testing networks, showcasing web projects, or exploring IoT, this tool gives you the flexibility to do it all. 
    It’s easily adaptable for various purposes—serve web applications, demo single-page apps (SPAs), or set up captive portals for network security testing.
  </p>
</div>

## Index <a name="index"></a>

- [Hardware](#hardware)
  - [Purchase](#purchase-device)
  - [Build your own](#build-your-own)
- [Firmware Setup](#firmware-setup)
  - [Connecting to PC](#connecting)
  - [Installing Firmware](#installing-firmware)
- [Software Setup](#software-setup)
  - [Installing Software](#installing-software)
  - [User Defined Settings](#user-defined-settings)
  - [Button Functions](#button-functions)
- [Development](#development)
  - [Requirements](#requirements)
  - [Development Setup](#development-setup)
  - [Scripts](#scripts)
- [Licensing](#licensing)
- [Wrapping Up](#wrapping-up)

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

## Hardware <a name="hardware"></a>

### Purchase device <a name="purchase-device"></a>

You can purchase a fully assembled Pico-Portal device exclusively from the Lambda shop here: 

https://www.lambda.guru/shop

### Build your own (parts list) <a name="build-your-own"></a>

| Part | Description | Link |
| :--- | :---------- | :--- |
| Raspberry Pi Pico W | The Raspberry Pi Pico W is a low-cost, high-performance microcontroller board built around the RP2040 chip. It features a dual-core ARM Cortex-M0+ processor with 264KB of SRAM and 2MB of flash memory. The Pico W also includes a built-in Wi-Fi module, making it an excellent choice for IoT projects. | [ThePiHut](https://thepihut.com/products/raspberry-pi-pico-w?variant=41952994787523) |
| Pimoroni Pico Display Pack | A lovely, bright 18-bit capable 240x135 pixel IPS display and fits the Pico perfectly. We've surrounded it with four tactile buttons so you can easily interface your Pico with your human fingers and an RGB LED that you can use as an indicator, for notifications or just for adding extra rainbows. | [Pimoroni](https://shop.pimoroni.com/products/pico-display-pack) |
| Pimoroni Pico Display Pack 2.0 | This 18-bit capable 320x240 pixel IPS display adheres majestically to the back of your Pico, and has lush colours and great viewing angles. Just like our original Display Pack, we've surrounded it with four tactile buttons so you can use your human fingers (or other non-human appendages) to interface with your Pico. There's also an RGB LED that you can use as an indicator, for notifications or just for adding extra rainbows. | [Pimoroni](https://shop.pimoroni.com/products/pico-display-pack-2-0) |

> ![Info][img-info] **Note:** A screen is optional but highly recommended for this project. The Pimoroni screen is a great choice for this project as it fits the Raspberry Pi Pico W perfectly and is easy to use. You can run the project without a screen, but you will not be able to see the real-time connection information.

<p align="right">[ <a href="#index">Index</a> ]</p>

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

## Firmware Setup <a name="firmware-setup"></a>

### Connecting to PC <a name="connecting"></a>

To connect your Raspberry Pi Pico W to your PC for firmware installation, follow these steps:

1. Make sure your Raspberry Pi Pico is not connected to any power source.

2. Hold down the BOOTSEL button on your Pico.

3. Connect the Pico to your computer using a Micro USB cable.

4. Release the BOOTSEL button. The device should appear on your computer as a USB Mass Storage Device.

> ![Info][img-info] **Note:** You only need to do this for Firmware installation. After the firmware is installed, you can connect your Pico to your computer without holding the BOOTSEL button.

### Installing the Pimoroni MicroPython Firmware <a name="installing-firmware"></a>

To install MicroPython on your Raspberry Pi Pico W after [connecting to your computer](#connecting-to-computer), follow these steps:

1. Download the latest Pimoroni Pico W UF2 file "picow-vXX.YY.ZZ-pimoroni-micropython.uf2" from the official releases:

   - https://github.com/pimoroni/pimoroni-pico/releases

2. Connect your Raspberry Pi Pico W to your PC, see [Connecting to PC](#connecting-to-pc).

3. Drag and drop the UF2 file onto the RPI-RP2 drive. This will program the MicroPython firmware onto your Pico.

4. Wait for a few seconds. The board will automatically reboot. Your Pico will now be running MicroPython.

<p align="right">[ <a href="#index">Index</a> ]</p>

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

## Software Setup <a name="software-setup"></a>

### Installing Software <a name="installing-software"></a>

> ![Info][img-info] **Note:** This project uses Node.js. Make sure you have Node.js installed on your system before proceeding.

1. Install project dependencies:
    
    ```bash
    npm install
    ```

2. Install Thonny IDE:

   - https://thonny.org/

3. Open Thonny IDE and connect to your Raspberry Pi Pico W via USB.

4. Copy the contents from `src/` (this repo) to the root of your Raspberry Pi Pico W using the Thonny IDE.

    > ![Info][img-info] **Note:** Be sure the "src/modules/" is copied and that the folder exists.

5. Unplug your Raspberry Pi Pico W from your computer and connect it to a power source.

6. Your Raspberry Pi Pico W will now boot up and display the Pico Portal interface on the Pimoroni screen.

### User Defined Settings <a name="user-defined-settings"></a>

You can customize the Pico Portal settings by editing the `src/options.py` file. The settings are as follows:

```python
{
    "wifi_ssid": "WiFi",
    "wifi_password": "",
    "wifi_domain": "setup.local",
    "display_type": "DISPLAY_PICO_DISPLAY"
}
```

| Setting | Description |
| :------ | :---------- |
| `wifi_ssid` | The SSID of the Wi-Fi network you want to create. |
| `wifi_password` | The password for the Wi-Fi network you want to create. Leave blank for an open network. |
| `wifi_domain` | The domain name for the captive portal. |
| `display_type` | The type of display you are using. Options are `DISPLAY_PICO_DISPLAY` or `DISPLAY_PICO_DISPLAY_2`. |

### Button Functions <a name="button-functions"></a>

The Pico Portal has four buttons that can be used to interact with the device. The button functions are as follows:

| Button | Function |
| :----- | :------- |
| `A` | Scroll up one line of the displayed log. Hold to scroll up faster. |
| `X` | Scroll down one line of the displayed log. Hold to scroll down faster. |
| `B` | Scroll to the top of the page of the displayed log. |
| `Y` | Scroll to the bottom of the page of the displayed log. |

Button layout:

```bash
 Pico Display       Pico Display 2.0
|=============|  |=====================|
|             |  |   (B)         (A)   |
|  (B)   (A)  |  | ------------------- |
| ----------- |  | |                 | |
| |         | |  | |                 | |
| |         | |  | |                 | |
| |         | |  | |                 | |
| |         | |  | |                 | |
| |         | |  | |                 | |
| ----------- |  | |                 | |
|  (Y)   (X)  |  | ------------------- |
|    (LED)    |  |   (Y)  (LED)  (X)   |
|=============|  |=====================|
```

<p align="right">[ <a href="#index">Index</a> ]</p>

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

## Development <a name="development"></a>

### Requirements <a name="requirements"></a>

Make sure the following are installed on your system before you begin:

- [Node.js][url-node-js]
- [Python][url-python]
- [Thonny IDE][url-thonny-ide]

### Development Setup <a name="development-setup"></a>

Using a terminal, follow these steps to set up the development environment:

1. Fork and clone the repository:

    ```bash
    git clone
    ```

2. Install project dependencies. This will install the required Node.js packages for running `setup.ts` which will download the required asset files to the `src/modules` folder. Run in the root of the project:

    ```bash
    npm install
    ```

3. Run the python setup script. This will download the files for linting (flake8), formatting (black), and pre-commit hooks (pre-commit). Basically everything we need for enforcing code quality.

    ```bash
    lint:install
    ```

4. Program, test, and debug the project using the Thonny IDE.

5. Commit (pre commit hooks should run and verify the code) and push your changes.

6. Create a pull request [here][url-pull-requests].

Thank you for contributing!

### Scripts <a name="scripts"></a>

    <!-- "build": "tsc",
    "format": "python3 -m black src/",
    "lint": "python3 -m flake8 --show-source --ignore E501 src/",
    "lint:install": "python3 -m pip install -r requirements.txt",
    "postinstall": "ts-node setup.ts" -->

| Script | Description |
| :----- | :---------- |
| `format` | Formats the Python code using Black. |
| `lint` | Lints the Python code using Flake8. |
| `lint:install` | Installs the required Python packages for linting and formatting. |
| `postinstall` | Downloads the required asset files to the `src/modules` folder. |

<p align="right">[ <a href="#index">Index</a> ]</p>

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

## Licensing <a name="licensing"></a>

This project is licensed under the **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)** License. See the [LICENSE.md](LICENSE.md) file for the pertaining license text.

`SPDX-License-Identifier: CC-BY-NC-4.0`

<p align="right">[ <a href="#index">Index</a> ]</p>

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

## Wrapping Up <a name="wrapping-up"></a>

I hope you enjoy this project as much as I enjoyed working on it. If you have any questions, please let me know by opening an issue [here][url-new-issue].

| Type                                                                      | Info                                                                      |
| :------------------------------------------------------------------------ | :------------------------------------------------------------------------ |
| <img width="48" src=".github/images/ng-icons/email.svg" />                | webmaster@codytolene.com                                                  |
| <img width="48" src=".github/images/simple-icons/buymeacoffee.svg" />     | https://www.buymeacoffee.com/codytolene                                   |
| <img width="48" src=".github/images/simple-icons/bitcoin-btc-logo.svg" /> | [bc1qfx3lvspkj0q077u3gnrnxqkqwyvcku2nml86wmudy7yf2u8edmqq0a5vnt][url-btc] |

Fin. Happy programming friend!

Cody Tolene

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

<!-- IMAGE REFERENCES -->

[img-info]: .github/images/ng-icons/info.svg
[img-warning]: .github/images/ng-icons/warn.svg

<!-- LINK REFERENCES -->

[url-btc]: https://explorer.btc.com/btc/address/bc1qfx3lvspkj0q077u3gnrnxqkqwyvcku2nml86wmudy7yf2u8edmqq0a5vnt
[url-new-issue]: https://github.com/CodyTolene/Pico-Portal/issues
[url-node-js]: https://nodejs.org/
[url-pull-requests]: https://github.com/CodyTolene/Pico-Portal/pulls
[url-python]: https://www.python.org/
[url-thonny-ide]: https://thonny.org/

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
