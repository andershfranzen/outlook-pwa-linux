.PHONY: all package release test clean

all: package

package:
	./scripts/build-deb.sh

release:
	./tests/test.sh
	./scripts/prepare-release.sh
	./tests/test-release.sh

test:
	./tests/test.sh

clean:
	rm -rf build/root
