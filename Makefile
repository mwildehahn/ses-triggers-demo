.PHONY: package

build:
	docker build -t lunohq/email-processing functions/email-processing

package: build
	docker run -v `pwd`/functions/email-processing/vendored:/vendored lunohq/email-processing

