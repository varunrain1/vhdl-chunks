library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

package filter_coeffs_pkg is
  constant COEFF_WIDTH : positive := 16;
  constant NUM_TAPS    : positive := 89;
  type coeff_array_t is array (0 to NUM_TAPS-1) of signed(COEFF_WIDTH-1 downto 0);
  constant FIR_COEFFS : coeff_array_t := (
    to_signed(2, 16),  -- 0.00014748
    to_signed(1, 16),  -- 0.00008043
    to_signed(-3, 16),  -- -0.00020170
    to_signed(-6, 16),  -- -0.00034566
    to_signed(0, 16),  -- 0.00000000
    to_signed(9, 16),  -- 0.00055366
    to_signed(9, 16),  -- 0.00052235
    to_signed(-6, 16),  -- -0.00034378
    to_signed(-18, 16),  -- -0.00107999
    to_signed(-8, 16),  -- -0.00049197
    to_signed(18, 16),  -- 0.00107279
    to_signed(27, 16),  -- 0.00164163
    to_signed(0, 16),  -- -0.00000000
    to_signed(-36, 16),  -- -0.00220833
    to_signed(-32, 16),  -- -0.00194390
    to_signed(20, 16),  -- 0.00120409
    to_signed(59, 16),  -- 0.00358545
    to_signed(26, 16),  -- 0.00155739
    to_signed(-53, 16),  -- -0.00325471
    to_signed(-79, 16),  -- -0.00479441
    to_signed(0, 16),  -- 0.00000000
    to_signed(99, 16),  -- 0.00604494
    to_signed(85, 16),  -- 0.00517750
    to_signed(-51, 16),  -- -0.00313004
    to_signed(-149, 16),  -- -0.00912330
    to_signed(-64, 16),  -- -0.00389008
    to_signed(131, 16),  -- 0.00800318
    to_signed(191, 16),  -- 0.01163935
    to_signed(0, 16),  -- -0.00000000
    to_signed(-237, 16),  -- -0.01443680
    to_signed(-202, 16),  -- -0.01232670
    to_signed(122, 16),  -- 0.00745768
    to_signed(358, 16),  -- 0.02184969
    to_signed(154, 16),  -- 0.00941278
    to_signed(-323, 16),  -- -0.01968553
    to_signed(-480, 16),  -- -0.02932191
    to_signed(0, 16),  -- 0.00000000
    to_signed(645, 16),  -- 0.03935626
    to_signed(586, 16),  -- 0.03575837
    to_signed(-386, 16),  -- -0.02356579
    to_signed(-1276, 16),  -- -0.07790237
    to_signed(-657, 16),  -- -0.04012035
    to_signed(1834, 16),  -- 0.11193864
    to_signed(4812, 16),  -- 0.29367431
    to_signed(6144, 16),  -- 0.37497877
    to_signed(4812, 16),  -- 0.29367431
    to_signed(1834, 16),  -- 0.11193864
    to_signed(-657, 16),  -- -0.04012035
    to_signed(-1276, 16),  -- -0.07790237
    to_signed(-386, 16),  -- -0.02356579
    to_signed(586, 16),  -- 0.03575837
    to_signed(645, 16),  -- 0.03935626
    to_signed(0, 16),  -- 0.00000000
    to_signed(-480, 16),  -- -0.02932191
    to_signed(-323, 16),  -- -0.01968553
    to_signed(154, 16),  -- 0.00941278
    to_signed(358, 16),  -- 0.02184969
    to_signed(122, 16),  -- 0.00745768
    to_signed(-202, 16),  -- -0.01232670
    to_signed(-237, 16),  -- -0.01443680
    to_signed(0, 16),  -- -0.00000000
    to_signed(191, 16),  -- 0.01163935
    to_signed(131, 16),  -- 0.00800318
    to_signed(-64, 16),  -- -0.00389008
    to_signed(-149, 16),  -- -0.00912330
    to_signed(-51, 16),  -- -0.00313004
    to_signed(85, 16),  -- 0.00517750
    to_signed(99, 16),  -- 0.00604494
    to_signed(0, 16),  -- 0.00000000
    to_signed(-79, 16),  -- -0.00479441
    to_signed(-53, 16),  -- -0.00325471
    to_signed(26, 16),  -- 0.00155739
    to_signed(59, 16),  -- 0.00358545
    to_signed(20, 16),  -- 0.00120409
    to_signed(-32, 16),  -- -0.00194390
    to_signed(-36, 16),  -- -0.00220833
    to_signed(0, 16),  -- -0.00000000
    to_signed(27, 16),  -- 0.00164163
    to_signed(18, 16),  -- 0.00107279
    to_signed(-8, 16),  -- -0.00049197
    to_signed(-18, 16),  -- -0.00107999
    to_signed(-6, 16),  -- -0.00034378
    to_signed(9, 16),  -- 0.00052235
    to_signed(9, 16),  -- 0.00055366
    to_signed(0, 16),  -- 0.00000000
    to_signed(-6, 16),  -- -0.00034566
    to_signed(-3, 16),  -- -0.00020170
    to_signed(1, 16),  -- 0.00008043
    to_signed(2, 16)  -- 0.00014748
  );
end package filter_coeffs_pkg;
