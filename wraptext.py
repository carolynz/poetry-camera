# 'text' is the input string to wrap
# 'line_length' is the max # characters per line
def wrap_text(text, line_length):
  # split input text into individual lines
  lines = text.split('\n')
  wrapped_text = ''
  indent = '   '
  indent_length = len(indent)

  for line in lines:
    # split line into a list of words
    words = line.split()
    current_line = ''
    line_start = True #indicates start of a new line (no indent)

    for word in words:
      # Adjust line length considering the indent on lines after the first
      adjusted_line_length = line_length if line_start else line_length - indent_length

      # if length of current_line + length of next word is within max line length
      if len(current_line) + len(word) <= adjusted_line_length:

        # then keep adding current_line to this line
        current_line += word + ' '

      else:
        if line_start:
          # finish current_line, add it to our output wrapped_text
          # also adds extra spaces for next line's indent
          wrapped_text += current_line.strip() + '\n'
          line_start = False #after this, all will be indented
        else:
          # finish current_line with indent, add it to our output wrapped_text
          wrapped_text += indent + current_line.strip() + '\n'

        # start new current_line
        current_line = word + ' '

    # add last line to our output, with indent if it's not the first line
    if line_start:
      wrapped_text += current_line.strip() + '\n'
    else:
      wrapped_text += indent + current_line.strip() + '\n'

  return wrapped_text
