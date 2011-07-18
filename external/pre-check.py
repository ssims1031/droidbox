from xml.dom import minidom
import zipfile, StringIO, cPickle
from bytecode import SV, SVs
from struct import pack, unpack, calcsize
import bytecode

######################################################## AXML FORMAT ########################################################
# Translated from http://code.google.com/p/android4me/source/browse/src/android/content/res/AXmlResourceParser.java
# Thx
class StringBlock :
   def __init__(self, buff) :
      buff.read( 4 )

      self.chunkSize = SV( '<L', buff.read( 4 ) )
      self.stringCount = SV( '<L', buff.read( 4 ) )
      self.styleOffsetCount = SV( '<L', buff.read( 4 ) )
      #FIXME
      buff.read(4) # ?
      self.stringsOffset = SV( '<L', buff.read( 4 ) )
      self.stylesOffset = SV( '<L', buff.read( 4 ) )

      #print self.chunkSize, self.stringCount, self.styleOffsetCount, self.stringsOffset, self.stylesOffset

      self.m_stringOffsets = []

      for i in range(0, self.stringCount.get_value()) :
         self.m_stringOffsets.append( SV( '<L', buff.read( 4 ) ) )

      #print self.m_stringOffsets

      if self.styleOffsetCount.get_value() != 0 :
         raise("ooo")
     
      size = self.chunkSize.get_value() - self.stringsOffset.get_value()
      if self.stylesOffset.get_value() != 0 :
         size = self.stylesOffset.get_value() - self.stringsOffset.get_value()
      
      #print size, size % 4
      
      self.m_strings = []
      for i in range(0, size / 4) :
         self.m_strings.append( SV( '<L', buff.read( 4 ) ) )

      if self.stylesOffset.get_value() != 0 :
         raise("ooo")

      #print "string", len(self.m_stringOffsets), len(self.m_strings)

      #for i in range(0, len(self.m_stringOffsets)) :
      #   print repr( self.getRaw( i ) )

   def getRaw(self, idx) :
      if idx < 0 or self.m_stringOffsets == [] or idx >= len(self.m_stringOffsets) :
         return None

      #print idx, self.m_stringOffsets[ idx ]
      offset = self.m_stringOffsets[ idx ].get_value()
      length = self.getShort(self.m_strings, offset)

      data = ""
      while length > 0 :
         offset += 2
         data += pack( "<B", self.getShort(self.m_strings, offset) )
         length -= 1
     
      return data

   def getShort(self, array, offset) :
      value = array[offset/4].get_value()
      if (offset%4)/2 == 0 :
         return value & 0xFFFF
      else :
         return value >> 16

ATTRIBUTE_IX_NAMESPACE_URI = 0
ATTRIBUTE_IX_NAME = 1 
ATTRIBUTE_IX_VALUE_STRING = 2
ATTRIBUTE_IX_VALUE_TYPE = 3 
ATTRIBUTE_IX_VALUE_DATA = 4
ATTRIBUTE_LENGHT = 5

CHUNK_AXML_FILE = 0x00080003 
CHUNK_RESOURCEIDS = 0x00080180
CHUNK_XML_FIRST = 0x00100100
CHUNK_XML_START_NAMESPACE = 0x00100100
CHUNK_XML_END_NAMESPACE = 0x00100101
CHUNK_XML_START_TAG = 0x00100102
CHUNK_XML_END_TAG = 0x00100103
CHUNK_XML_TEXT = 0x00100104
CHUNK_XML_LAST = 0x00100104

START_DOCUMENT = 0
END_DOCUMENT = 1
START_TAG = 2
END_TAG = 3
TEXT = 4
class AXMLParser :
   def __init__(self, raw_buff) :
      self.reset()

      self.buff = bytecode.BuffHandle( raw_buff )

      self.buff.read(4)
      self.buff.read(4)

      self.sb = StringBlock( self.buff )

      self.m_resourceIDs = []
      self.m_prefixuri = {}
      self.m_uriprefix = {}
      self.m_prefixuriL = []

   def reset(self) :
      self.m_event = -1
      self.m_lineNumber = -1
      self.m_name = -1
      self.m_namespaceUri = -1
      self.m_attributes = []
      self.m_idAttribute = -1
      self.m_classAttribute = -1
      self.m_styleAttribute = -1

   def next(self) :
      self.doNext()
      return self.m_event
   
   def doNext(self) :
      if self.m_event == END_DOCUMENT :
         return
      
      event = self.m_event
      
      self.reset()
      while 1 :
         chunkType = -1

         # Fake END_DOCUMENT event.
         if event == END_TAG :
            pass #raise("oo")

         if event == START_DOCUMENT :
            chunkType = CHUNK_XML_START_TAG
         else :
            if self.buff.end() == True :
               self.m_event = END_DOCUMENT
               break
            chunkType = SV( '<L', self.buff.read( 4 ) ).get_value()

     #    print "CHUNKTYPE ", hex(chunkType)

         if chunkType == CHUNK_RESOURCEIDS :
            chunkSize = SV( '<L', self.buff.read( 4 ) ).get_value()
            if chunkSize < 8 or chunkSize%4 != 0 :
               raise("ooo")

            for i in range(0, chunkSize/4-2) :
               self.m_resourceIDs.append( SV( '<L', self.buff.read( 4 ) ) )

            continue

         if chunkType < CHUNK_XML_FIRST or chunkType > CHUNK_XML_LAST :
            raise("ooo")

         # Fake START_DOCUMENT event.
         if chunkType == CHUNK_XML_START_TAG and event == -1 :
            self.m_event = START_DOCUMENT 
            break

         self.buff.read( 4 ) #/*chunkSize*/
         lineNumber = SV( '<L', self.buff.read( 4 ) ).get_value()
         self.buff.read( 4 ) #0xFFFFFFFF

         if chunkType == CHUNK_XML_START_NAMESPACE or chunkType == CHUNK_XML_END_NAMESPACE :
            if chunkType == CHUNK_XML_START_NAMESPACE :
               prefix = SV( '<L', self.buff.read( 4 ) ).get_value()
               uri = SV( '<L', self.buff.read( 4 ) ).get_value()

               self.m_prefixuri[ prefix ] = uri
               self.m_uriprefix[ uri ] = prefix
               self.m_prefixuriL.append( (prefix, uri) )
            else :
               self.buff.read( 4 )
               self.buff.read( 4 )
               (prefix, uri) = self.m_prefixuriL.pop()
               del self.m_prefixuri[ prefix ]
               del self.m_uriprefix[ uri ]
            
            continue


         self.m_lineNumber = lineNumber 

         if chunkType == CHUNK_XML_START_TAG :
            self.m_namespaceUri = SV( '<L', self.buff.read( 4 ) ).get_value()
            self.m_name = SV( '<L', self.buff.read( 4 ) ).get_value()
            self.buff.read( 4 ) #flags
            attributeCount = SV( '<L', self.buff.read( 4 ) ).get_value()
            self.m_idAttribute = (attributeCount>>16) - 1
            attributeCount = attributeCount & 0xFFFF
            self.m_classAttribute = SV( '<L', self.buff.read( 4 ) ).get_value()
            self.m_styleAttribute = (self.m_classAttribute>>16) - 1
                                            
            self.m_classAttribute = (self.m_classAttribute & 0xFFFF) - 1
           
            for i in range(0, attributeCount*ATTRIBUTE_LENGHT) :
               self.m_attributes.append( SV( '<L', self.buff.read( 4 ) ).get_value() )

            for i in range(ATTRIBUTE_IX_VALUE_TYPE, len(self.m_attributes), ATTRIBUTE_LENGHT) :
               self.m_attributes[i] = (self.m_attributes[i]>>24)

            self.m_event = START_TAG
            break

         if chunkType == CHUNK_XML_END_TAG :
            self.m_namespaceUri = SV( '<L', self.buff.read( 4 ) ).get_value()
            self.m_name = SV( '<L', self.buff.read( 4 ) ).get_value()
            self.m_event = END_TAG
            break

         if chunkType == CHUNK_XML_TEXT :
            self.m_name = SV( '<L', self.buff.read( 4 ) ).get_value()
            self.buff.read( 4 ) #?
            self.buff.read( 4 ) #?
                                                                                                                                                                        
            self.m_event = TEXT
            break

   def getPrefixByUri(self, uri) :
      try :
         return self.m_uriprefix[ uri ]
      except KeyError :
         return -1

   def getPrefix(self) :
      try : 
         return self.sb.getRaw(self.m_prefixuri[ self.m_namespaceUri ])
      except KeyError :
         return ""

   def getName(self) :
      if self.m_name == -1 or (self.m_event != START_TAG and self.m_event != END_TAG) :
         return ""

      return self.sb.getRaw(self.m_name)

   def getText(self) :
      if self.m_name == -1 or self.m_event != TEXT :
         return ""

      return self.sb.getRaw(self.m_name)

   def getNamespacePrefix(self, pos) :
      prefix = self.m_prefixuriL[ pos ][0]
      return self.sb.getRaw( prefix )

   def getNamespaceUri(self, pos) :
      uri = self.m_prefixuriL[ pos ][1]
      return self.sb.getRaw( uri )

   def getAttributeOffset(self, index) :
      if self.m_event != START_TAG :
         raise("Current event is not START_TAG.")

      offset = index * 5
      if offset >= len(self.m_attributes) :
         raise("Invalid attribute index")

      return offset

   def getAttributeCount(self) :
      if self.m_event != START_TAG :
         return -1

      return len(self.m_attributes) / ATTRIBUTE_LENGHT

   def getAttributePrefix(self, index) :
      offset = self.getAttributeOffset(index)
      uri = self.m_attributes[offset+ATTRIBUTE_IX_NAMESPACE_URI]

      prefix = self.getPrefixByUri( uri )
      if prefix == -1 :
         return ""

      return self.sb.getRaw( prefix )

   def getAttributeName(self, index) :
      offset = self.getAttributeOffset(index)
      name = self.m_attributes[offset+ATTRIBUTE_IX_NAME]

      if name == -1 :
         return ""

      return self.sb.getRaw( name )

   def getAttributeValueType(self, index) :
      offset = self.getAttributeOffset(index)
      return self.m_attributes[offset+ATTRIBUTE_IX_VALUE_TYPE]

   def getAttributeValueData(self, index) :
      offset = self.getAttributeOffset(index)
      return self.m_attributes[offset+ATTRIBUTE_IX_VALUE_DATA]

   def getAttributeValue(self, index) :
      offset = self.getAttributeOffset(index)
      valueType = self.m_attributes[offset+ATTRIBUTE_IX_VALUE_TYPE]
      if valueType == TYPE_STRING :
         valueString = self.m_attributes[offset+ATTRIBUTE_IX_VALUE_STRING]
         return self.sb.getRaw( valueString )
      #int valueData=m_attributes[offset+ATTRIBUTE_IX_VALUE_DATA];
      #return TypedValue.coerceToString(valueType,valueData);
      raise("ooo")

TYPE_ATTRIBUTE = 2
TYPE_DIMENSION = 5
TYPE_FIRST_COLOR_INT = 28
TYPE_FIRST_INT = 16
TYPE_FLOAT = 4
TYPE_FRACTION = 6
TYPE_INT_BOOLEAN = 18
TYPE_INT_COLOR_ARGB4 = 30
TYPE_INT_COLOR_ARGB8 = 28
TYPE_INT_COLOR_RGB4 = 31
TYPE_INT_COLOR_RGB8 = 29
TYPE_INT_DEC = 16
TYPE_INT_HEX = 17
TYPE_LAST_COLOR_INT = 31
TYPE_LAST_INT = 31
TYPE_NULL = 0
TYPE_REFERENCE = 1
TYPE_STRING = 3
class AXMLPrinter :
   def __init__(self, raw_buff) :
      self.axml = AXMLParser( raw_buff )
      self.xmlns = False

      self.buff = ""

      while 1 :
         _type = self.axml.next()
#         print "tagtype = ", _type

         if _type == START_DOCUMENT :
#            print "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
            self.buff += "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
         elif _type == START_TAG :
#            print "<%s%s" % ( self.getPrefix( self.axml.getPrefix() ), self.axml.getName() ),
            self.buff += "<%s%s\n" % ( self.getPrefix( self.axml.getPrefix() ), self.axml.getName() )

            if self.xmlns == False :      
#               print " xmlns:%s=\"%s\" " % ( self.axml.getNamespacePrefix( 0 ), self.axml.getNamespaceUri( 0 ) )
               self.buff += "xmlns:%s=\"%s\"\n" % ( self.axml.getNamespacePrefix( 0 ), self.axml.getNamespaceUri( 0 ) )
               self.xmlns = True

            for i in range(0, self.axml.getAttributeCount()) :
#               print "%s%s=\"%s\"" % ( self.getPrefix( self.axml.getAttributePrefix(i) ), self.axml.getAttributeName(i), self.getAttributeValue( i ) )
               self.buff += "%s%s=\"%s\"\n" % ( self.getPrefix( self.axml.getAttributePrefix(i) ), self.axml.getAttributeName(i), self.getAttributeValue( i ) )

#            print ">"
            self.buff += ">\n"

         elif _type == END_TAG :
#            print "</%s%s>" % ( self.getPrefix( self.axml.getPrefix() ), self.axml.getName() )
            self.buff += "</%s%s>\n" % ( self.getPrefix( self.axml.getPrefix() ), self.axml.getName() )

         elif _type == TEXT : 
#            print "%s" % self.axml.getText()
            self.buff += "%s\n" % self.axml.getText()

         elif _type == END_DOCUMENT :
            break

         else :
            raise("ooo")

   def getBuff(self) :
      return self.buff

   def getPrefix(self, prefix) :
      if prefix == None or len(prefix) == 0 :
         return ""

      return prefix + ":"

   def getAttributeValue(self, index) :
      _type = self.axml.getAttributeValueType(index)
      _data = self.axml.getAttributeValueData(index)

      if _type == TYPE_STRING :
         return self.axml.getAttributeValue( index )

      if _type == TYPE_ATTRIBUTE :
         return "?%s%08X" % (self.getPackage(_data), _data)

      if _type == TYPE_REFERENCE :
         return "@%s%08X" % (self.getPackage(_data), _data)

      if _type == TYPE_FLOAT :
         #String.valueOf(Float.intBitsToFloat(data));
         raise("ooo")

      if _type == TYPE_INT_HEX :
         return "0x%08X" % _data

      if _type == TYPE_INT_BOOLEAN :
         if _data == 0 :
            return "false"
         return "true"

      if _type == TYPE_DIMENSION :
         #return Float.toString(complexToFloat(data)) + DIMENSION_UNITS[data & TypedValue.COMPLEX_UNIT_MASK];
         raise("ooo")

      if _type == TYPE_FRACTION :
         #return Float.toString(complexToFloat(data)) + FRACTION_UNITS[data & TypedValue.COMPLEX_UNIT_MASK];
         raise("ooo")

      if _type >= TYPE_FIRST_COLOR_INT and _type <= TYPE_LAST_COLOR_INT :
         return "#%08X" % data

      if _type >= TYPE_FIRST_INT and _type <= TYPE_LAST_INT :
         return "%d" % _data

      return "<0x%X, type 0x%02X>" % (_data, _type)

   def getPackage(self, id) :
      if id >> 24 == 1 :
         return "android:"
      return ""

filename = "DroidBoxTests.apk"
xml = {}
permissions = []
activities = []
activityaction = {}
services = []
packageNames = []
recvs = []
recvsaction = {}

fd = open( filename, "rb" )
raw = fd.read()
fd.close()
zip = zipfile.ZipFile( StringIO.StringIO( raw ) )

for i in zip.namelist() :
 if i == "AndroidManifest.xml" :
    try :
       xml[i] = minidom.parseString( zip.read( i ) )
    except :
       xml[i] = minidom.parseString( AXMLPrinter( zip.read( i ) ).getBuff() )
       for item in xml[i].getElementsByTagName('manifest'):
          packageNames.append( str( item.getAttribute("package") ) )
       for item in xml[i].getElementsByTagName('uses-permission'):
          permissions.append( str( item.getAttribute("android:name") ) )
       for item in xml[i].getElementsByTagName('receiver'):
          recvs.append( str( item.getAttribute("android:name") ) )
          for child in item.getElementsByTagName('action'):
              recvsaction[str( item.getAttribute("android:name") )] = (str( child.getAttribute("android:name") ))
       for item in xml[i].getElementsByTagName('service'):
          services.append( str( item.getAttribute("android:name") ) )
       for item in xml[i].getElementsByTagName('activity'):
          activities.append( str( item.getAttribute("android:name") ) )
          for child in item.getElementsByTagName('action'):
              activityaction[str( item.getAttribute("android:name") )] = (str( child.getAttribute("android:name") ))
                              
print "\nPackage name\n============"
print packageNames
print "\nPermissions\n==========="
print permissions
print "\nActivities\n=========="
print activities
print activityaction
print "\nServices\n========"
print services
print "\nReceivers\n========="
print recvs
print recvsaction
print ''

"""
FILE = open("fridge.tmp", 'w')
cPickle.dump(permissions, FILE)
FILE.close()

FILE = open("fridge.tmp", 'r')
inFridgeFile = cPickle.load(FILE)
FILE.close()
print inFridgeFile
"""