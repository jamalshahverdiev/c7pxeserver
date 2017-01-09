#!/usr/bin/env python

import sys
import os
import jinja2
from termcolor import colored, cprint
from fabric.api import *
from fabric.tasks import execute
import getpass

codepath = os.getcwd()
jinjadir = codepath+'/jinja2temps/'
outputdir = codepath+'/output/'

templateLoader = jinja2.FileSystemLoader( searchpath=jinjadir )
templateEnv = jinja2.Environment( loader=templateLoader )

TEMPDMASQ = 'dnsmasq.conf.j2'
TEMPIFACE = 'ifcfg-name.j2'
TEMPVNC = 'default.j2'

tempdmasq = templateEnv.get_template( TEMPDMASQ )
tempiface = templateEnv.get_template( TEMPIFACE )
tempvnc = templateEnv.get_template( TEMPVNC )

pxeserver = colored('PXE server', 'green', attrs=['bold', 'underline'])
ipaddress = colored('IP address', 'green', attrs=['bold', 'underline'])
username = colored('username', 'green', attrs=['bold', 'underline'])
password = colored('password', 'magenta', attrs=['bold', 'underline'])
successfully = colored('successfully', 'green', attrs=['bold', 'underline'])
centos = colored('CentOS', 'yellow', attrs=['bold', 'underline'])
enter = colored('Enter', 'cyan', attrs=['bold', 'underline'])

print('Script will install and configure '+pxeserver+'.')
print('It needs '+ipaddress+', '+username+' and '+password+' to start process.')
env.host_string = raw_input('Please enter '+ipaddress+' of '+pxeserver+': ')
env.user = raw_input('Please enter '+username+' for UNIX/Linux server: ')
env.password = getpass.getpass('Please enter '+password+' for '+pxeserver+': ')

def tempconfiger(iface, uuidforiface, hwaddr, vncpass):
    tempifaceVars = { "iface" : iface,
            "uuidforiface" : uuidforiface,
            "hwaddr": hwaddr,
            "vncpass": vncpass,
            }

    outputifaceText = tempiface.render( tempifaceVars )
    outputdmasqText = tempdmasq.render( tempifaceVars )
    outputvncText = tempvnc.render( tempifaceVars )

    with open(outputdir+'ifcfg-'+iface+'', 'wb') as ifaceout:
        ifaceout.write(outputifaceText)

    with open(outputdir+'dnsmasq.conf', 'wb') as dmasqout:
        dmasqout.write(outputdmasqText)

    with open(outputdir+'default', 'wb') as vncout:
        vncout.write(outputvncText)

def variables():
    global osver
    osver = run('uname -s')
    global lintype
    lintype = run('cat /etc/centos-release | awk \'{ print $1 }\'')
    global getcosver
    getcosver = run('rpm -q --queryformat \'%{VERSION}\' centos-release')
    global netcards
    netcards = run('cat /proc/net/dev | egrep -v \'Inter|face|lo\' | cut -f1 -d\':\'')
    global checkcdrom
    checkcdrom = run('mount -o loop /dev/cdrom /mnt')
    global mountedcdrom
    mountedcdrom = run('cat /proc/mounts | grep iso9660 | head -1 | awk \'{ print $3 }\'')
    global netcardcount
    netcardcount = run('cat /proc/net/dev | egrep -v \'Inter|face|lo\' | cut -f1 -d\':\' | wc -l')

servicelist = ['dnsmasq', 'vsftpd', 'network', 'firewalld', 'ntpd']

commands = ['yum update -y; yum -y install epel-release',
         'yum -y install net-tools bind-utils nload iftop wget git htop tcpdump ntpdate ntp',
         'yum -y install dnsmasq syslinux tftp-server vsftpd',
         'cp -r /usr/share/syslinux/* /var/lib/tftpboot',
         'mv /etc/dnsmasq.conf /etc/dnsmasq.conf.backup',
         'mkdir /var/lib/tftpboot/pxelinux.cfg',
         'mount -o loop /dev/cdrom /mnt',
         'mkdir /var/lib/tftpboot/centos7',
         'cp /mnt/images/pxeboot/vmlinuz /var/lib/tftpboot/centos7; cp /mnt/images/pxeboot/initrd.img /var/lib/tftpboot/centos7',
         'cp -r /mnt/* /var/ftp/pub/; chmod -R 755 /var/ftp/pub',
         'umount /mnt',
         'ntpdate 0.asia.pool.ntp.org']

def prints():
    print('Please '+enter+' name of internal and external network card names!!!')
    print('Internal network card will be used to configure DHCP server!!!')
    print('External network card will be used to configure NAT for internal subnet 10.0.0.0/24!!!')
    print('')
    print(netcards)
    print('')

def vnc_creds():
    print('')
    print('Please remember entered VNC '+password+'. This '+password+' will be used to connect to the server with VNC viewer.')
    print('')
    global vncguipass
    vncguipass = getpass.getpass('  Please '+enter+' '+password+' of the VNC server: ')
    global vncguipass1
    vncguipass1 = getpass.getpass('  Please repeat '+password+' of the VNC server: ')
    print('')

    while vncguipass != vncguipass1:
        print('')
        print(' Entered passwords must be the same. Please '+enter+' passwords again. ')
        vncguipass = getpass.getpass('  Please '+enter+' '+password+' of the VNC server: ')
        vncguipass1 = getpass.getpass('  Please repeat '+password+' of the VNC server: ')

        if vncguipass == vncguipass1:
            print('')
            print(' The '+password+' set successfully!')
            break
        print(' Entered passwords must be the same. Please '+enter+' passwords again. ')

def put_func():
    put(outputdir+'default', '/var/lib/tftpboot/pxelinux.cfg/default')
    put(outputdir+'ifcfg-'+intiface+'', '/etc/sysconfig/network-scripts/')
    put(outputdir+'dnsmasq.conf', '/etc/dnsmasq.conf')

def after_install_vars():
    global dmasqservice
    dmasqservice = run('ps waux| grep dnsmasq | grep -v grep | awk \'{ print $11 }\'')
    global vsftpdservice
    vsftpdservice = run('ps waux| grep vsftpd | grep -v grep | head -1 | awk \'{ print $11 }\'')
    global netcardip
    netcardip = run('ifconfig '+intiface+' | grep \'inet \' | awk \'{ print $2 }\'')

def natconfiger(intiface, extiface):
    run('systemctl start firewalld')
    run('echo \'net.ipv4.ip_forward = 1\' >> /etc/sysctl.d/ip_forward.conf ; sysctl -w net.ipv4.ip_forward=1')
    run('firewall-cmd --permanent --zone=external --change-interface='+extiface+'')
    run('firewall-cmd --permanent --zone=internal --change-interface='+intiface+'')
    run('firewall-cmd --set-default-zone=external')
    run('firewall-cmd --complete-reload')
    run('firewall-cmd --zone=external --add-masquerade --permanent')
    run('firewall-cmd --permanent --direct --passthrough ipv4 -t nat -I POSTROUTING -o '+extiface+' -j MASQUERADE -s 10.0.0.0/24')
    run('firewall-cmd --permanent --zone=internal --add-service={dhcp,tftp,dns,http,https,nfs,ntp,ssh,ftp,vnc-server}')
    run('firewall-cmd --permanent --zone=internal --add-port={69/udp,4011/udp}')
    #firewall-cmd --get-active-zones
    #firewall-cmd --list-all
    #firewall-cmd --get-zones
    #firewall-cmd --zone=internal --list-all
    #firewall-cmd --zone=external --list-all
    #firewall-cmd --get-zone-of-interface=ens36
    #firewall-cmd --info-zone=internal
    run('firewall-cmd --complete-reload')

with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
    variables()

    if osver == 'Linux' and lintype == 'CentOS':
        print('')
        print('OS type Linux '+centos+'.')

        if getcosver == '6':
            print('Version is "6"!')
        elif getcosver == '7':
            print('Version is "7"!')
            print('')

        if checkcdrom == '':
            pass
        elif mountedcdrom == 'iso9660':
            print('CDROM is already mounted!!!')
            sys.exit()
        else:
            print('Please insert CentOS7 image to your server CDROM and try again!!!')
            sys.exit()

        if netcardcount < '2':
            print('Your server network card must be minimum 2. Please add second network card and try again!!!')
            sys.exit()
        else:
            pass

        print('  Please be patient script will install and configure all needed packages!!!')
        print('')

	for comm in commands:
            run(comm)

        prints()
        extiface = raw_input('Please '+enter+' external network card name for NAT configuration: ')
        intiface = raw_input('Please '+enter+' internal network card name for DHCP sevrer: ')
        hwaddr = run('ifconfig '+intiface+'| grep ether | awk \'{ print $2 }\'')
        vnc_creds()
        uuidforiface = run('uuidgen '+intiface+'')
        tempconfiger(intiface, uuidforiface, hwaddr, vncguipass)
        natconfiger(intiface, extiface)
        put_func()

        for service in servicelist:
            run('systemctl restart '+service+'; systemctl enable '+service+'')

        after_install_vars()

        if dmasqservice == '/usr/sbin/dnsmasq' and vsftpdservice == '/usr/sbin/vsftpd' and netcardip == '10.0.0.1':
            print('All services '+successfully+' installed and configured!')
            sys.exit()
        else:
            print('There is some problem with installation. One of the services (dnsmasq, vsftpd) or '+intiface+' '+ipaddress+' is not configured properly!!!')
            print('Please check SeLinux, firewalld!!!')
            sys.exit()
