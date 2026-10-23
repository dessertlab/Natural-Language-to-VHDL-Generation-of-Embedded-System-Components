case state is when "00" => q <= a and b; when "01" => q <= a or b; when "10" => q <= not a; when "11" => q <= a xor b; end case; end module;
