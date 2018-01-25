import System
import clr
white=System.Reflection.Assembly.LoadFrom('./TestStack.White.dll')
castle=System.Reflection.Assembly.LoadFrom('./Castle.Core.dll')
clr.AddReference(white)
clr.AddReference(castle)
import TestStack.White
import TestStack.White.Factory
import TestStack.White.UIItems.WindowItems
import TestStack.White.UIItems.MenuItems
import TestStack.White;
import TestStack.White.AutomationElementSearch;
import TestStack.White.Bricks;
import TestStack.White.Configuration;
import TestStack.White.Drawing;
import TestStack.White.Factory;
import TestStack.White.Finder;
import TestStack.White.InputDevices;
import TestStack.White.Interceptors;
import TestStack.White.Mappings;
import TestStack.White.Recording;
import TestStack.White.ScreenMap;
import TestStack.White.Sessions;
import TestStack.White.SystemExtensions;
import TestStack.White.UIA;
import TestStack.White.UIItemEvents;
import TestStack.White.UIItems;
import TestStack.White.UIItems.Actions;
import TestStack.White.UIItems.Container;
import TestStack.White.UIItems.Custom;
import TestStack.White.UIItems.Finders;
import TestStack.White.UIItems.ListBoxItems;
import TestStack.White.UIItems.ListViewItems;
import TestStack.White.UIItems.MenuItems;
import TestStack.White.UIItems.PropertyGridItems;
import TestStack.White.UIItems.Scrolling;
import TestStack.White.UIItems.TabItems;
import TestStack.White.UIItems.TableItems;
import TestStack.White.UIItems.TreeItems;
import TestStack.White.UIItems.WindowItems;
import TestStack.White.UIItems.WindowStripControls;
import TestStack.White.UIItems.WPFUIItems;
import TestStack.White.Utility;
import TestStack.White.WindowsAPI;
import time


mouse=TestStack.White.InputDevices.Mouse
i=1
while 1:
    mouse.LeftDown()
    mouse.
    time.sleep(10)
    print i
    i=i+1
    