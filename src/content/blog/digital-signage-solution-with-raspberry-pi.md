---
title: "Digital Signage Solution with Raspberry Pi"
date: 2017-02-20
author: "Khaled Zaky"
categories: ["code"]
description: "How to build a wireless digital signage solution using a Raspberry Pi and Screenly. Manage and display content on any screen, remotely and on the cheap."
---

Digital Signage has been around for quiet a while. You can find digital signs everywhere today across restaurants, retailers, fintess clubs, and even on the streets. The uses cases would vary and span across displaying the menu at your local fast food restaurant to covering buildings with ads to in-store advertisement.

The following how-to guide will allow you to wirelessly manage and display content from webpages, images, and/or videos on any 1080p TV or display. This is very similar to the kind of digital signage to the menus you see in any major fast-food restaurant chain you enter today.

## Why use Screenly and a Raspberry Pi?
This was what was needed to reinvent the industry. What we wanted was an affordable, modern and lightweight solution. The solution is fairly easy to manage and extremely inexpensive. Less than $100 in parts, 2 hours of your time (thanks to these instructions), and no subscription fees (unless you really want to go Pro). Not only that, the hardware was powerful enough to support full-HD playback. So there you go, a simple recipe of Screenly and Raspberry Pi will get you up and running with a turn-key digital signage solution.


## 8 Easy Steps
1. A TV or a Display of your choice.
2. A Raspberry Pi, or a kit like this one, which includes all the hardware you need.
3. Download the current Screenly OS image here.
4. Use your computer to write the image to the micro SD card: Instructions for Win/Mac/Linux.
5. Insert the micro SD in the Pi, connect the Ethernet, HDMI, USB hub and Wi-Fi dongle (optional), and lastly the power.
6. The Pi should boot and display the IP address of the ethernet adapter.
7. Take note of this address.
8. I have used a USB cable from the Pi to the TV with success. However, this probably isn't recommended, for multiple reasons:

	* Insufficient power from the TV USB port for reliable operation
	* The Pi will turn off whenever the TV turns off, increasing wear and tear on the file system
	* You have to wait for the Pi to boot every time the TV turns on.

**Optional:** Configure Wi-Fi:
1. Connect to the Pi via ssh. On a Mac or Linux use the command `ssh pi@x.x.x.x [enter]`, and enter password `"raspberry"`
2. Use an editor like nano or vi (both included in the image) to modify `network.ini`
3. `ifup wlan0`
4. Type `sudo reboot [enter]` to restart the Pi, and disconnect the ethernet cable.
5. It should reboot and display an IP address as before. You are now connected via WiFi.
6. Connect to the new IP address from your browser using the URL: `http://x.x.x.x:8080`

**Optional:** If you get a black border around the image, try disabling overscan:
1. Using SSH, connect to the Pi again
2. Edit the `/boot/config.txt` file.
3. Remove the `#` before the `disable_overscan=1` command to uncomment and activate the command

For more info visit [Screenly's Website](https://www.screenlyapp.com/ose.html)
