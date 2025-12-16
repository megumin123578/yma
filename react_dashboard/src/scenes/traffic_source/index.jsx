import { Box } from '@mui/material'
import Header from '../../components/Header'
import TrafficSourceChart from '../../components/TrafficSource'

const TrafficSource = () => {
  return (
    <Box m="20px">
      <Header title="Traffic Source" subtitle="Views By Traffic Source" />
      <Box height="75vh">
        <TrafficSourceChart />
      </Box>
    </Box>
  );
};

export default TrafficSource;

