name = thumber
version = $(shell git describe --abbrev=0)
full_version = $(shell git describe --always)

rpm:
	git archive --format=tar --prefix=$(name)-$(full_version)/ HEAD | gzip -9 \
	    > $(name)-$(full_version).tar.gz
	rpmbuild -ta $(name)-$(full_version).tar.gz \
		--define 'full_version $(full_version)' \
		--define 'version $(version)' \
		--define 'release $(subst -,_,$(full_version))'

deb:
	dpkg-buildpackage -A -uc -us

