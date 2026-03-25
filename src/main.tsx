import React from 'react';
import ReactDOM from 'react-dom/client';
import { createTheme, MantineColorsTuple, MantineProvider } from '@mantine/core';
import '@mantine/core/styles.css';
import App from './App';
import './styles.css';

const ocean: MantineColorsTuple = [
  '#eaf3fb',
  '#d7e8f7',
  '#b6d3ef',
  '#92bee7',
  '#73addf',
  '#60a0da',
  '#5598d8',
  '#4284c1',
  '#3374ad',
  '#215f95',
];

const theme = createTheme({
  fontFamily: '"Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
  primaryColor: 'ocean',
  colors: {
    ocean,
  },
  defaultRadius: 'xl',
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <MantineProvider theme={theme}>
    <App />
  </MantineProvider>,
);
