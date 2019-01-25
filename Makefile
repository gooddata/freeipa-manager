tarball:
	git archive --format=tar HEAD | gzip > freeipa-manager.tar.gz

.PHONY: tarball
