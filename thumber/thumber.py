"""Thumber Library
Author Hannu Valtonen"""
import Image
import struct
import StringIO
try:
    import json
except:
    import simplejson as json

INDEX_VERSION = 1

class Thumber(object):
    """Thumber librarys main class, use this if you want to use everything"""
    def __init__(self, thumbnail_sizes = None, reserved_keys = None, plugins = None):
        if thumbnail_sizes:
            self.thumbnail_sizes = thumbnail_sizes
        else:
            self.thumbnail_sizes = ((128, 128), (64, 64), (32, 32)) #default sizes
        if plugins:
            self.plugins = plugins
        else:
            self.plugins = [self.create_thumbnails]
        self.thumb_indexer = ThumberIndex(reserved_keys)

    def create_thumbs_and_index(self, data_blob, extra_keys_dict = None):
        """Create thumbnails and an index, and add possible additional keys to the file index"""
        result_dict = {}
        for plugin in self.plugins:
            result_dict.update(plugin(data_blob))
        return self.thumb_indexer.create_thumbnail_blob_with_index(result_dict, extra_keys_dict = extra_keys_dict)

    def create_thumbnails(self, data_blob):
        """Create required thumbnails, sizes are set in object instance creation time"""
        image = Image.open(StringIO.StringIO(data_blob))
        result_dict = {}
        for thumbnail_size in self.thumbnail_sizes:
            image.thumbnail(thumbnail_size, Image.ANTIALIAS)
            file_buffer = StringIO.StringIO()
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(file_buffer, format = 'JPEG')
            result_dict[str(thumbnail_size[0]) + "x" + str(thumbnail_size[1]) + "xjpg"] = file_buffer.getvalue()
        return result_dict

class ThumberIndex(object):
    """Class for creating files with n thumbnails and an access index"""
    def __init__(self, reserved_keys):
        if reserved_keys:
            self.reserved_keys = reserved_keys
        else:
            self.reserved_keys = ['version']

    def create_thumbnail_blob_with_index(self, result_dict, extra_keys_dict = None):
        """Expects a dict like {'128x128xjpg': thumbnail_data, '64x64xjpg': thumbnail2_data, 'my_reserved_key': 1}"""
        header, data, current_offset = {'version': INDEX_VERSION}, [], 0
        if extra_keys_dict:
            result_dict.update(extra_keys_dict)
        else:
            extra_keys_dict = {}

        for k, v in result_dict.items():
            if k not in self.reserved_keys + extra_keys_dict.keys():
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

    def read_thumbnail_blob_with_index(self, data_blob, thumbnail_key = None, extra_reserved_keys = None):
        """Expects a data blob created by create_thumbnail_file_with_index
        If thumbnail_key has been given, returns the blob in question
        otherwise return a thumbnail_dict with all available thumbnail sizes
        """
        if not extra_reserved_keys:
            extra_reserved_keys = []

        header_length = int(struct.unpack("H", data_blob[:2])[0])
        header = json.loads(data_blob[2:2 + header_length])
        total_header_length = header_length + 2

        if thumbnail_key:
            start_offset, stop_offset = header[thumbnail_key]
            return data_blob[total_header_length + start_offset:total_header_length + stop_offset]

        return_dict = {}
        for k, v in header.items():
            if k not in self.reserved_keys + extra_reserved_keys:
                return_dict[k] = data_blob[total_header_length + v[0]:total_header_length + v[1]]
            else:
                return_dict[k] = v
        return return_dict

def help_msg():
    """Help msg function for thumber"""
    print "Help:"
    print "    thumber store <input_image_file> <output_thumbnail_index_file>"
    print "    thumber load <input_thumbnail_index> <size> <output_thumbnail_image.jpg>"
    print "Thumber Copyright Hannu Valtonen 2011"

def main():
    """Entry point for thumber console script"""
    import sys
    if len(sys.argv) >= 4:
        a = Thumber()
        input_data = file(sys.argv[2], "rb").read()
        if sys.argv[1] == "store":
            data_blob = a.create_thumbs_and_index(input_data)
            output_filename = sys.argv[3]
        elif sys.argv[1] == "load" and len(sys.argv) == 5:
            data_blob = a.thumb_indexer.read_thumbnail_blob_with_index(input_data, sys.argv[3] + "xjpg")
            output_filename = sys.argv[4]
        else:
            help_msg()
            sys.exit(0)
        output_file = file(output_filename, "wb")
        output_file.write(data_blob)
        output_file.close()
    else:
        help_msg()

if __name__ == "__main__":
    main()
