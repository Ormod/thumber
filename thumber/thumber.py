import Image
import hashlib
import os
import struct
import StringIO
try:
    import json
except:
    import simplejson as json

INDEX_VERSION = 1

class Thumber(object):
    def __init__(self, thumbnail_sizes = None, reserved_additional_keys = None, plugins = None):
        if thumbnail_sizes:
            self.thumbnail_sizes = thumbnail_sizes
        else:
            self.thumbnail_sizes = ((128,128), (64,64), (32,32)) #default sizes
        if reserved_additional_keys:
            self.reserved_additional_keys = reserved_additional_keys
        else:
            self.reserved_additional_keys = []
        if plugins:
            self.plugins = plugins
        else:
            self.plugins = [self.create_thumbnails]

    def create_thumbs_and_index(self, data_blob, reserved_additional_keys = None):
        """Create thumbnails and an index, and add possible additional keys to the file index"""
        result_dict = {}
        for plugin in self.plugins:
            result_dict.update(plugin(data_blob))
        if reserved_additional_keys:
            result_dict.update(reserved_additional_keys)
        return self.create_thumbnail_blob_with_index(result_dict)

    def create_thumbnails(self, data_blob):
        """Create required thumbnails, sizes are set in object instance creation time"""
        im = Image.open(StringIO.StringIO(data_blob))
        result_dict = {}
        for thumbnail_size in self.thumbnail_sizes:
            im.thumbnail(thumbnail_size, Image.ANTIALIAS)
            file_buffer = StringIO.StringIO()
            if im.mode != "RGB":
                im = im.convert("RGB")
            im.save(file_buffer, format = 'JPEG')
            result_dict[str(thumbnail_size[0]) + "x" + str(thumbnail_size[1]) + "xjpg"] = file_buffer.getvalue()
        return result_dict

    def create_thumbnail_blob_with_index(self, result_dict):
        """Expects a dict like {'128x128xjpg': thumbnail_data, '64x64xjpg': thumbnail2_data, 'my_reserved_key': 1}"""
        header, data, current_offset = {'version': INDEX_VERSION}, [], 0
        for k, v in result_dict.items():
            if k not in self.reserved_additional_keys:
                offsets = [current_offset, current_offset + len(v)]
                header[k] = offsets
                current_offset += len(v)
                data.append(v)
            else:
                header[k] = v
        json_header = json.dumps(header)
        data_list = [struct.pack("H", len(json_header)), json_header]
        data_list.extend(data)
        return ''.join(data_list)

    def read_thumbnail_blob_with_index(self, data_blob, thumbnail_key = None):
        """Expects a data blob created by create_thumbnail_file_with_index
        If thumbnail_key has been given, returns the blob in question
        otherwise return a thumbnail_dict with all available thumbnail sizes
        """
        header_length = int(struct.unpack("H", data_blob[:2])[0])
        header = json.loads(data_blob[2:2 + header_length])
        total_header_length = header_length + 2

        if thumbnail_key:
            start_offset, stop_offset = header[thumbnail_key]
            return data_blob[total_header_length + start_offset:total_header_length + stop_offset]

        return_dict = {}
        for k, v in header.items():
            if k not in self.reserved_keys:
                return_dict[k] = data_blob[total_header_length + v[0]:total_header_length + v[1]]
            else:
                return_dict[k] = v
        return return_dict

def help():
    print "Help:"
    print "    thumber store <input_image_file> <output_thumbnail_index_file>"
    print "    thumber load <input_thumbnail_index> <size> <output_thumbnail_image.jpg>"
    print "Thumber Copyright Hannu Valtonen 2011"

def main():
    import sys, time
    start_time = time.time()
    if len(sys.argv) >= 4:
        a = Thumber()
        input_data = file(sys.argv[2], "rb").read()
        if sys.argv[1] == "store":
            data_blob = a.create_thumbs_and_index(input_data)
            output_filename = sys.argv[3]
        elif sys.argv[1] == "load" and len(sys.argv) == 5:
            data_blob = a.read_thumbnail_blob_with_index(input_data, sys.argv[3] + "xjpg")
            output_filename = sys.argv[4]
        else:
            help()
            sys.exit(0)
        output_file = file(output_filename, "wb")
        output_file.write(data_blob)
        output_file.close()
    else:
        help()
    print "Thumber took %.3fs to run" % (time.time() - start_time)

if __name__ == "__main__":
    main()
