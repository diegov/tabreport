#!/bin/sh

dbus-send --print-reply --dest=net.diegoveralli.tabreport \
          /net/diegoveralli/tabreport \
          net.diegoveralli.tabreport.TabReport
