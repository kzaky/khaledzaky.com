---
layout:     post
title:      "Digital Signage Solution with Raspberry Pi"
subtitle:   "wirelessly manage and display content on any display"
date:       2017-02-20 12:00:00
author:     "Khaled Zaky"
header-img: "img/post-bg-01.jpg"
tags: [web, jekyll, jude, yara, khaled]
categories: [web, jekyll]
---

<h2 class="section-heading">Digital Signage?</h2>

<p>Digital Signage has been around for quiet a while. You can find digital signs everywhere today across restaurants, retailers, fintess clubs, and even on the streets. The uses cases would vary and span across displaying the menu at your local fast food restaurant to covering buildings with ads to in-store advertisement.</p>

<p>The following how-to guide will allow you to wirelessly manage and display content from webpages, images, and/or videos on any 1080p TV or display. This is very similar to the kind of digital signage to the menus you see in any major fast-food restaurant chain you enter today.</p>

<h2 class="section-heading">Why use Screenly and a Raspberry Pi to accomplish this?</h2>
<p>This was what was needed to reinvent the industry. What we wanted was an affordable, modern and lightweight solution. The solution is fairly easy to manage and extremely inexpensive. Less than $100 in parts, 2 hours of your time (thanks to these instructions), and no subscription fees (unless you really want to go Pro). Not only that, the hardware was powerful enough to support full-HD playback. So there you go, a simple recipe of Screenly and Raspberry Pi will get you up and running with a turn-key digital signage solution.</p>


<h2 class="section-heading">8 Easy Steps</h2>
<p>
<ol>
 	<li>A TV or a Display of your choice.</li>
 	<li>A Raspberry Pi, or a kit like this one, which includes all the hardware you need.</li>
 	<li>Download the current Screenly OS image here.</li>
 	<li>Use your computer to write the image to the micro SD card: Instructions for Win/Mac/Linux.</li>
 	<li>Insert the micro SD in the Pi, connect the Ethernet, HDMI, USB hub and Wi-Fi dongle (optional), and lastly the power.</li>
 	<li>The Pi should boot and display the IP address of the ethernet adapter.</li>
 	<li>Take note of this address.</li>
 	<li>I have used a USB cable from the Pi to the TV with success. However, this probably isn’t recommended, for multiple reasons:
<ul>
 	<li>Insufficient power from the TV USB port for reliable operation</li>
 	<li>The Pi will turn off whenever the TV turns off, increasing wear and tear on the file system</li>
 	<li>You have to wait for the Pi to boot every time the TV turns on.</li>
</ul>
</li>
</ol>
</p>

<p>
<em><b>Optional:</b> Configure Wi-Fi:</em>
<ol>
 	<li>Connect to the Pi via ssh. On a Mac or Linux use the command "ssh pi@x.x.x.x [enter]", and enter password “raspberry”</li>
 	<li>Use an editor like nano or vi (both included in the image) to modify network.ini</li>
 	<li>ifup wlan0</li>
 	<li>Type "sudo reboot [enter]" to restart the Pi, and disconnect the ethernet cable.</li>
 	<li>It should reboot and display an IP address as before. You are now connected via WiFi.</li>
 	<li>Connect to the new IP address from your browser using the URL: http://x.x.x.x:8080</li>
</ol>
</p>

<p>
<em><b>Optional:</b> If you get a black border around the image, try disabling overscan:</em>
<ol>
<li>Using SSH, connect to the Pi again</li>
<li>Edit the /boot/config.txt file.</li>
<li>Remove the # before the disable_overscan=1 command to uncomment and activate the command</li>
</ol>
</p>

<p>For more info visit <a href="https://www.screenlyapp.com/ose.html">Screenly's Website</a>.</p>