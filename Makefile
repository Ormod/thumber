deb:
	dpkg-buildpackage -A -uc -us

clean:
	$(RM) -r *.egg-info/ build/ dist/

test:
	pylint -E -rn -iy -eW0102 -eW0402 -eW0611 -eW0621 -eW0622 thumber
