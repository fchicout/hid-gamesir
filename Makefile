KDIR ?= /lib/modules/$(shell uname -r)/build
PWD := $(CURDIR)

default:
	$(MAKE) -C $(KDIR) M=$(PWD) modules

clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean
	rm -f src/*.o src/.*.cmd

install:
	$(MAKE) -C $(KDIR) M=$(PWD) modules_install
	depmod -a

.PHONY: default clean install
