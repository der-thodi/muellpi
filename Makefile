init:
	pip3 install -r requirements.txt

clean:
	$(RM) *.ics

.PHONY: init
