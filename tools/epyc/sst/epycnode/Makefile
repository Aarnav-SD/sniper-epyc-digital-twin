SST_CONFIG := $(SST_CORE_HOME)/bin/sst-config

CXX := $(shell $(SST_CONFIG) --CXX)
CXXFLAGS := $(shell $(SST_CONFIG) --ELEMENT_CXXFLAGS)
LDFLAGS := $(shell $(SST_CONFIG) --ELEMENT_LDFLAGS)

TARGET := libepyctwin.so
SOURCES := epyc_node.cc

all: $(TARGET)

$(TARGET): $(SOURCES) epyc_node.h
	$(CXX) $(CXXFLAGS) -o $@ $(SOURCES) $(LDFLAGS)

clean:
	rm -f $(TARGET)

.PHONY: all clean
